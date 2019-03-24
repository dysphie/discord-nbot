import os

from discord import Guild
from discord.ext import commands
from discord.ext.commands import Context

from logger import log
from markov_generator import fabricate_sentence, create_model

bot = commands.Bot(command_prefix='.')

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')


@bot.event
async def on_ready():
    log.info('Nbot ready')


@bot.command()
async def be(ctx: Context, nickname: str) -> object:
    if not nickname:
        return
    guild: Guild = ctx.channel.guild
    user = guild.get_member_named(nickname)
    if not user:
        await ctx.send('User %s not found.' % nickname)
        return

    content = fabricate_sentence(user.id)

    # todo webhook id from env vars
    webhook = await ctx.channel.create_webhook(name='Temporary')
    await webhook.send(content=content, username=nickname, avatar_url=user.avatar_url)
    await webhook.delete()


@bot.command()
async def add(ctx: Context, nickname: str):
    lvh = 102140663629361152
    q = 232909513378758657
    allowed_ids = [lvh, q]
    if ctx.author.id in allowed_ids:
        user = ctx.channel.guild.get_member_named(nickname)
        await ctx.send('Updating model for %s' % nickname)
        create_model(user.id)
        await ctx.send('Updated model for %s' % nickname)


bot.run(BOT_TOKEN)
