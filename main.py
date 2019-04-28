'''
TODO:
- Merge db.cache and db.model_cache
- Fix regex filter not working
'''

import os
import re
import time

import discord
import markovify
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound

from chat_importer import start_import
from colorpicker import reactionships, remove_colors, isrgbcolor
from db import chat, cache
from logger import log
from louds import handle_loud_message, import_loud_messages
from markov_generator import create_model, fabricate_message_from_history, get_model_for_user, \
    DiscordText, get_model_for_users
from util import strip_mentions
from webhooks import send_webhook_to_channel

ENV_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
if not ENV_BOT_TOKEN:
    raise Exception('You must set the DISCORD_BOT_TOKEN environment variable')

bot = commands.Bot(command_prefix='.')
cleverbot = Cleverbot()


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
    if message.content.lower().startswith('botc '):
        cleverbot.send(message.content[5:])
        response = cleverbot.get_message()
        await message.channel.send(response)
        return

    # YELL
    await handle_loud_message(message)


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


@bot.command()
async def ping(ctx):
    await ctx.send(':ping_pong:')


# Impersonate user
@bot.command()
async def be(ctx, identity):
    user = await find_user(ctx, identity)
    if user is None:
        await ctx.send(f'User {identity} not found.')
        return

    model = get_model_for_user(user.id)
    await _send_model_messages(ctx, model, user)


@bot.command()
async def combine(ctx: Context, query: str):
    # ".be endigy+endig+endi+q+q+q+ q ++++++kosmo"
    # translates to a list of user ids, bails when user is not found

    identities = {x.strip() for x in query.split('+') if x.strip()}
    user_ids = set()

    for identity in identities:
        user = await find_user(ctx, identity)
        if user:
            user_ids.add(user.id)
        else:
            await ctx.channel.send(f'User `{identity}` not found.')
            return

    user_count = len(user_ids)
    if user_count > 10:
        await ctx.channel.send(f'**{user_count}** users? Processing power doesn\'t grow on trees mate')
        return

    if user_count < 2:
        await ctx.channel.send('Please specify at least 2 users')
        return
    models = get_model_for_users(user_ids)
    log.debug('Combining models for %d users', user_count)
    t = time.time()
    combined_model = markovify.combine(models)
    log.info('Combining models took %s', time.time() - t)
    await _send_model_messages(ctx, combined_model)


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


# Update / initialize the 'loud messages' database
@bot.command()
async def importlouds(ctx):
    if is_admin(ctx):
        log.info('Starting import of loud messages')
        amount = import_loud_messages()
        await ctx.send('Imported %d loud messages' % amount)
    else:
        log.info(f'{ctx.author} tried to import loud messages but is not administrator')


# Update database with new user
@bot.command()
async def adduser(ctx, nickname: str):
    if is_admin(ctx):
        user = await find_user(ctx, nickname)
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
        if user.nick and user.nick.lower().startswith(identity) or user.name.lower().startswith(identity):
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


async def _send_model_messages(ctx: Context, model: DiscordText, user: discord.User = None):
    for i in range(3):
        content = model.make_sentence(tries=100)
        if content:
            content = strip_mentions(content)
            if user:
                display_name = user.display_name.rjust(2, '~')
                await send_webhook_to_channel(ctx.channel, content, display_name, user.avatar_url)
            else:
                await ctx.send(content)
            time.sleep(1)


bot.run(ENV_BOT_TOKEN)
