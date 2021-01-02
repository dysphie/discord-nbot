from io import BytesIO
import discord
from discord.ext import commands

class Inspire(commands.Cog, name="Inspire"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @commands.command()
    async def inspire(self, ctx):
        async with self.session.get('https://inspirobot.me/api?generate=true') as r:
            if r.status != 200:
                return await ctx.error('Could not fetch file...')

            imgurl = await r.read()
            await ctx.send(imgurl)


def setup(bot):
    bot.add_cog(Inspire(bot))
