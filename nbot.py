import os
from typing import Optional

from discord import Webhook, User, RequestsWebhookAdapter, Permissions
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound

from chat_importer import start_import
from logger import log
from markov_generator import fabricate_sentence, create_model, fabricate_message_from_history

bot = commands.Bot(command_prefix='.')

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
WEBHOOK_ID = int(os.environ.get('WEBHOOK_ID'))
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN')


@bot.event
async def on_ready():
    log.info('Nbot ready')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    await ctx.send('An error occurred while executing the command: %s' % error)
    raise error


@bot.command()
async def be(ctx: Context, nickname: str = None) -> object:
    if not nickname:
        return
    user = find_user(ctx, nickname)
    if not user:
        await ctx.send('User %s not found.' % nickname)
        return

    content = fabricate_sentence(user.id)
    webhook = Webhook.partial(WEBHOOK_ID, WEBHOOK_TOKEN, adapter=RequestsWebhookAdapter())
    webhook.send(content, username=_get_valid_user_name(user), avatar_url=user.avatar_url)


@bot.command()
async def add(ctx: Context, nickname: str):
    if is_admin(ctx):
        user = find_user(ctx, nickname)
        if user:
            name = _get_valid_user_name(user)
            await ctx.send('Updating model for %s' % name)
            create_model(user.id)
            await ctx.send('Updated model for %s' % name)
        else:
            await ctx.send('No user found with name "%s"' % nickname)


@bot.command()
async def random(ctx: Context):
    message = fabricate_message_from_history([msg.content async for msg in ctx.channel.history(limit=300)])
    await ctx.send(message)


@bot.command()
async def i(ctx: Context):
    if is_admin(ctx):
        await start_import(ctx)


def is_admin(ctx: Context):
    author: User = ctx.author
    permissions: Permissions = author.permissions_in(ctx.channel)
    return permissions.administrator


def find_user(ctx: Context, name: str) -> Optional[User]:
    member = ctx.channel.guild.get_member_named(name)
    if member:
        return member
    name = name.lower()
    for member in ctx.channel.guild.members:
        if member.nick and name in member.nick.lower() or name in member.name.lower():
            return member


def _get_valid_user_name(user: User) -> str:
    if user.nick and len(user.nick) > 1:
        return user.nick
    return user.name


bot.run(BOT_TOKEN)
