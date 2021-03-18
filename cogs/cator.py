import discord
from discord.ext import commands
from bs4 import BeautifulSoup


class Cator(commands.Cog, name="Cator"):

    url = 'https://thesecatsdonotexist.com'

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @commands.command()
    async def cat(self, ctx):
        async with self.session.get(url) as r:
            if r.status != 200:
                return await ctx.error('Could not fetch file...')

            text = await resp.read()
            soup = BeautifulSoup(text.decode('utf-8'), 'html5lib')
            img_url = soup.find("img", {"id": "1"})['src']

            embed = discord.Embed(color=0x7fffd4)
            embed.set_image(url=img_url)
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Cator(bot))
