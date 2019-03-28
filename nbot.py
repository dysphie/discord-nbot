import os
from typing import Optional

from discord import Webhook, User, RequestsWebhookAdapter
from discord.ext import commands
from discord.ext.commands import Context

from logger import log
from markov_generator import fabricate_sentence, create_model, fabricate_message_from_history

bot = commands.Bot(command_prefix='.')

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
WEBHOOK_ID = int(os.environ.get('WEBHOOK_ID'))
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN')


@bot.event
async def on_ready():
    log.info('Nbot ready')


@bot.command()
async def be(ctx: Context, nickname: str) -> object:
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
    lvh = 102140663629361152
    q = 232909513378758657
    allowed_ids = [lvh, q]
    if ctx.author.id in allowed_ids:
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
