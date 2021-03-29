import io

import discord
from discord.ext import commands


class Inspire(commands.Cog, name="Inspire"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @commands.command()
    async def inspire(self, ctx):
        async with self.session.get('https://inspirobot.me/api?generate=true') as r:

            quote_url = await r.text()
            async with self.session.get(quote_url) as r2:
                data = io.BytesIO(await r2.read())
                await ctx.send(file=discord.File(data, 'quote.png'))


def setup(bot):
    bot.add_cog(Inspire(bot))
