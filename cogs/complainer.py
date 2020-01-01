import aiohttp
from discord.utils import escape_mentions
from discord.ext import commands
from bs4 import BeautifulSoup


class Complainer(commands.Cog, name="Complainer"):

    def __init__(self, bot):
        self.bot = bot
        self.task = self.bot.loop.create_task(self.initialize())

    async def initialize(self):
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.task.cancel()
        self.session.close()

    @commands.command()
    async def complain(self, ctx, entity=None, gender='male'):

        if not entity or gender not in ['male', 'female', 'company']:
            await ctx.send("Usage: complain `entity` `male`/`female`/`company``")

        cookies = {'ACLG_agreed': ''}
        params = {
            'firstname': entity.title(),
            'gender': gender[:1],
            'shorttype': 'f',
            'pgraphs': 1
        }
        async with self.session.get('https://www.pakin.org/complaint', cookies=cookies, params=params) as r:
            if(r.status == 200):
                soup = BeautifulSoup(await r.text(), "html.parser")
                complaint = escape_mentions(soup.find('p').get_text())
                if complaint:
                    await ctx.send(complaint)


def setup(bot):
    bot.add_cog(Complainer(bot))
