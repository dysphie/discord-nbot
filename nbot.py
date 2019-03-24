import logging
import os

import discord
from discord.ext import commands

from markov_generator import fabricate_sentence, create_model

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(asctime)s - %(message)s')
bot = commands.Bot(command_prefix='.')

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')


@bot.event
async def on_ready():
    logging.info('Ready')


@bot.command()
async def be(ctx: discord.Webhook, *args) -> object:
    guild = ctx.channel.guild
    nickname = ' '.join(args)

    user = guild.get_member_named(nickname)
    if not user:
        return

    content = fabricate_sentence(user.id)

    # todo webhook id from env vars
    webhook = await ctx.channel.create_webhook(name='Temporary')
    await webhook.send(content=content, username=nickname, avatar_url=user.avatar_url)
    await webhook.delete()


@bot.command()
async def add(ctx, user_id: int):
    model = create_model(user_id)

    for i in range(5):
        logging.debug('TEST SENTENCE: ' + model.make_sentence(tries=100))


bot.run(BOT_TOKEN)
