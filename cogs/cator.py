import io
from random import choice, randint

import discord
from discord import slash_command
from discord.ext import commands


class Cator(commands.Cog, name="Cator"):

    url = 'https://thesecatsdonotexist.com'

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @slash_command(name="cat", description='Posts an AI generated picture of a cat')
    async def cat(self, ctx):

        folder = choice(['04', '05', '06'])
        catnum = randint(0, 5000)

        cat_url = f'https://d2ph5fj80uercy.cloudfront.net/{folder}/cat{catnum}.jpg'
        async with self.session.get(cat_url) as resp:
            data = io.BytesIO(await resp.read())
            await ctx.send(file=discord.File(data, 'cat.png'))


def setup(bot):
    bot.add_cog(Cator(bot))
