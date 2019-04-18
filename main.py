'''
TODO:
- Merge db.cache and db.model_cache
- Fix regex filter not working
'''

import os
import re
import time

import discord
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound

from chat_importer import start_import
from cleverbot import Cleverbot
from colorpicker import reactionships, remove_colors, isrgbcolor
from db import yells, chat, cache
from logger import log
from markov_generator import fabricate_sentence, create_model, fabricate_message_from_history
from webhooks import send_webhook_to_channel

ENV_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
if not ENV_BOT_TOKEN:
    raise Exception('You must set the DISCORD_BOT_TOKEN environment variable')

bot = commands.Bot(command_prefix='.')
cleverbot = None

user_mention = re.compile(r'<@!?[0-9]+>')


@bot.event
async def on_ready():
    print('Logged in as %s [ID: %s]' % (bot.user.name, bot.user.id))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    await ctx.send('An error occurred while executing the command: %s' % error)
    raise error


# Chat triggers
@bot.event
async def on_message(message):
    if message.author.bot:
        # Repost PatchBot's messages without ads
        if message.author.name == 'PatchBot' and message.author.discriminator == '0000':
            for embed in message.embeds:
                if not "This update is sponsored by" in embed.author.name:
                    await message.channel.send(embed=embed)
            await message.delete()

        # Ignore bots further
        return

    # Process any commands
    await bot.process_commands(message)

    # Talk to cleverbot
    if message.content.startswith('botc '):
        global cleverbot
        if not cleverbot:
            cleverbot = Cleverbot()
        cleverbot.send(message.content[5:])
        response = cleverbot.get_message()
        await message.channel.send(response)
        return

    # YELL
    if message.content.isupper() and len(message.content.split()) > 2:
        yells.insert_one({'msg': message.content})
        cursor = yells.aggregate([{'$sample': {'size': 1}}])
        for dic in cursor:
            await message.channel.send(dic.get('msg'))
            break


# Give color role from palette
@bot.event
async def on_raw_reaction_add(payload):
    channel = bot.get_channel(payload.channel_id)
    user = discord.utils.get(channel.guild.members, id=payload.user_id)
    if user.bot:
        return

    message = await channel.fetch_message(payload.message_id)
    emote = payload.emoji.id

    if emote not in reactionships.keys():
        return  # check if emote is on watch list
    await message.remove_reaction(payload.emoji, user)

    wanted_role = discord.utils.get(channel.guild.roles, id=reactionships.get(emote))
    if wanted_role in user.roles:
        return  # user already has this role

    await remove_colors(user)  # remove existing color roles
    await user.add_roles(wanted_role)


# Give color role from hex code
@bot.command()
async def hex(ctx, hex_code: str):
    if not isrgbcolor(hex_code):
        await ctx.send('Invalid hex color code')
        return

    guild = ctx.message.guild
    new_color = discord.Colour(int(hex_code, 16))

    # Make sure there's space first
    if not (len(guild.roles) < 250):
        await ctx.channel.send('All role slots are taken, cry me a river')
        return

    role = await guild.create_role(name='Custom: ' + hex_code, color=new_color)
    user = ctx.message.author

    await remove_colors(user)  # Remove any existing color roles
    await user.add_roles(role)


# Impersonate user
@bot.command()
async def be(ctx, identity):
    user = await find_user(ctx, identity)
    if user is None:
        await ctx.send(f'User {identity} not found.')
        return

    display_name = user.display_name
    while len(display_name) < 2:
        display_name += '~'
    for i in range(3):
        content = fabricate_sentence(user.id)

        # Completely remove mentions for now
        content = re.sub(user_mention, '', content)

        await send_webhook_to_channel(ctx.channel, content, display_name, user.avatar_url)
        time.sleep(1)


# Generate sentence based on current chat
@bot.command()
async def random(ctx):
    message = fabricate_message_from_history([msg.content async for msg in ctx.channel.history(limit=300)])
    await ctx.send(message)


# Update database with new messages
@bot.command()
async def addmessages(ctx):
    if is_admin(ctx):
        await start_import(ctx)
    else:
        log.info(f'{ctx.author} tried to import messages but is not administrator')


# Update database with new user
@bot.command()
async def adduser(ctx, nickname: str):
    if is_admin(ctx):
        user = find_user(ctx, nickname)
        if user:
            create_model(user.id)
            return True
    return False


# Alias a user id to a readable name
@bot.command()
async def alias(ctx, user_id: str = None, nickname: str = None):
    if is_admin(ctx):
        if not user_id:
            ctx.send('Missing argument user id')
        try:
            user_id = int(user_id)
            await _add_alias_to_user(ctx, user_id, nickname)
        except ValueError:
            if user_id == 'list':
                results = cache.find()
                await ctx.send('\n'.join(['%s: %s' % (r['_id'], r['n']) for r in results]))


def is_admin(ctx: Context):
    permissions = ctx.author.permissions_in(ctx.channel)
    return permissions.administrator


async def find_user(ctx, identity):

    # Search as user in current server
    for user in ctx.channel.guild.members:
        if user.nick and identity in user.nick.lower() or identity in user.name.lower():
            return user

    # Search as name in users cache
    substring = re.compile(fr'{identity}', re.I)
    result = cache.find_one({"n": substring})
    if not result:
        # Not found by name, search by user id
        try:
            result = cache.find_one({"_id": int(identity)})
        except ValueError:
            pass
    user_id = result and result.get("_id")
    if user_id:
        user = await bot.fetch_user(user_id)
        if user:
            return user

    try:
        identity = int(identity)
        return await _add_alias_to_user(ctx, identity)
    except ValueError:
        pass


async def _add_alias_to_user(ctx: Context, identity: int, hotname: str = None):
    user = await bot.fetch_user(identity)
    if not user:
        return

    if not hotname:
        hotname = f'{user.name}#{user.discriminator}'
    # Search as ID in chat log so we don't add users that don't exist
    result = chat.find_one({"a": identity})
    if result:
        cache.update_one({'_id': identity}, {'$set': {'n': hotname}}, upsert=True)
        embed = discord.Embed(description=f'**{identity}** may now be referred to as **{hotname}**', color=0x1abc9c)
        await ctx.channel.send(embed=embed)
        return user


async def get_nametag_from_id(user_id):
    user = await bot.fetch_user(user_id)
    return f'{user.name}#{user.discriminator}' if user else 'Deleted#0000'


bot.run(ENV_BOT_TOKEN)