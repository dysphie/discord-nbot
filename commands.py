import os
from typing import Optional
from discord import User, Permissions
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound
from cleverbot import Cleverbot
from chat_importer import start_import
from logger import log
from markov_generator import fabricate_sentence, create_model, fabricate_message_from_history
from webhooks import send_webhook_to_channel
from db import yells
from colorpicker import reactionships, remove_colors, isrgbcolor

ENV_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

bot = commands.Bot(command_prefix='.')
cleverbot = Cleverbot()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} [ID: {bot.user.id}]')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    await ctx.send('An error occurred while executing the command: %s' % error)
    raise error


# Chat triggers
@bot.event()
async def on_message(message):
    if message.author.bot: return

    # Talk to cleverbot
    if message.content.startswith('botc '):
        cleverbot.send(message.content[5:])
        while True:
            response = cleverbot.get_message()
            if response:
                await message.channel.send(response)
                return

    # YELL
    if message.content.isupper() and len(message.content.split()) > 2:
        yells.insert_one({ 'msg': message.content })
        cursor = db.yells.aggregate([{'$sample': {'size': 1}}]) 
        for dic in cursor:
            await message.channel.send( dic.get('msg') )
            break

    # Process any commands
    await bot.process_commands(message)


# Give color role from palette
@bot.event()
async def on_raw_reaction_add(payload):

    user = discord.utils.get(channel.guild.members, id=payload.user_id)
    if user.bot: return;

    message = await channel.get_message(payload.message_id)
    emote = payload.emoji.id

    if emote not in reactionships.keys(): return    # Check if emote is on watch list
    await message.remove_reaction(payload.emoji, user)

    wanted_role =  discord.utils.get(channel.guild.roles, id=reactionships.get(emote))

    if wanted_role in user.roles: return            # User already has that role
    await remove_colors(user)                       # Remove any existing color roles
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
async def be(ctx, *nickname):
    if not nickname:
        return
    user = find_user(ctx, nickname)
    if not user:
        await ctx.send('User %s not found.' % nickname)
        return

    content = fabricate_sentence(user.id)
    await send_webhook_to_channel(ctx.channel, content, nickname, user.avatar_url)


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

