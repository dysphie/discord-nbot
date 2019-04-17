import os
import time
from typing import Optional
import discord
from discord import User, Permissions
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound
from cleverbot import Cleverbot
from chat_importer import start_import
from logger import log
from markov_generator import fabricate_sentence, create_model, fabricate_message_from_history
from webhooks import send_webhook_to_channel
from db import yells, chat
from colorpicker import reactionships, remove_colors, isrgbcolor

ENV_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

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
    if message.content.startswith('botc '):
        cleverbot.send(message.content[5:])
        while True:
            response = cleverbot.get_message()
            if response:
                await message.channel.send(response)
                break

    # YELL
    if message.content.isupper() and len(message.content.split()) > 2:
        yells.insert_one({ 'msg': message.content })
        cursor = yells.aggregate([{'$sample': {'size': 1}}]) 
        for dic in cursor:
            await message.channel.send( dic.get('msg') )
            break


# Give color role from palette
@bot.event
async def on_raw_reaction_add(payload):

    channel = bot.get_channel(payload.channel_id)
    user =  discord.utils.get(channel.guild.members, id=payload.user_id)
    if user.bot: return;

    message = await channel.fetch_message(payload.message_id)
    emote = payload.emoji.id

    if emote not in reactionships.keys(): return # check if emote is on watch list
    await message.remove_reaction(payload.emoji, user)

    wanted_role =  discord.utils.get(channel.guild.roles, id=reactionships.get(emote))
    if wanted_role in user.roles: return # user already has this role

    await remove_colors(user) # remove existing color roles
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

    await remove_colors(user) # Remove any existing color roles
    await user.add_roles(role)

    
# Impersonate user
@bot.command()
async def be(ctx: Context, nickname: str = None) -> object:
    if not nickname:
        return
    user = await find_user(ctx, nickname)
    if user is None:
        await ctx.send('User %s not found.' % nickname)
        return

    for i in range(3):
        content = fabricate_sentence(user.id)
        display_name = user.display_name
        while len(display_name) < 2: display_name+='~'
        await send_webhook_to_channel(ctx.channel, content, display_name, user.avatar_url)
        time.sleep(1)


# Generate sentence based on current chat

'''
@bot.command()
async def random(ctx):
    message = fabricate_message_from_history([msg.content async for msg in ctx.channel.history(limit=300)])
    await ctx.send(message)
'''

# Update database with new messages
@bot.command()
async def addmessages(ctx):
    if is_admin(ctx):
        await start_import(ctx)
    else:
        log.info('Not starting import: user %s is not administrator', ctx.author)


# Update database with new user
@bot.command()
async def adduser(ctx, nickname: str):

    if is_admin(ctx):
        user = find_user(ctx, nickname)
        if user:
            name = _get_valid_user_name(user)
            await ctx.send('Updating model for %s' % name)
            create_model(user.id)
            await ctx.send('Updated model for %s' % name)
        else:
            await ctx.send('No user found with name "%s"' % nickname)

def is_admin(ctx: Context):
    permissions = ctx.author.permissions_in(ctx.channel)
    return permissions.administrator


async def find_user(ctx, lead):

    # Find by name inside guild
    user = ctx.channel.guild.get_member_named(lead)
    if user: return user

    # Find by loose name inside guild
    lead = lead.lower()
    for user in ctx.channel.guild.members:
        if user.nick and lead in user.nick.lower() or lead in user.name.lower():
            return user

    # Interpret as ID, lookup in our db
    user_id = int(lead)
    if chat.find_one({"a": user_id}):
        user = await bot.fetch_user(user_id)
        if user: return user


def _get_valid_user_name(user: User) -> str:
    if user.nick and len(user.nick) > 1:
        return user.nick
    return user.name

bot.run(ENV_BOT_TOKEN)
