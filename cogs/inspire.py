import io

import discord
from discord import slash_command
from discord.ext import commands


class Inspire(commands.Cog, name="Inspire"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @slash_command(name="inspire", description='Posts an AI generated inspirational quote')
    async def inspire(self, ctx):
        async with self.session.get('https://inspirobot.me/api?generate=true') as r:
            quote_url = await r.text()
            async with self.session.get(quote_url) as r2:
                data = io.BytesIO(await r2.read())
                await ctx.respond(file=discord.File(data, 'quote.png'))


def setup(bot):
    bot.add_cog(Inspire(bot))
