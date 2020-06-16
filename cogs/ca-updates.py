import discord
from discord.ext import tasks, commands
import re
import aiohttp
from bs4 import BeautifulSoup

PATCH_NOTES_URL = 'https://forums.valofe.com/forum/combat-arms-reloaded/official-news-updates-aa/updates-aa'
EMBED_BANNER = "https://forums.valofe.com/filedata/fetch?id=17922&d=1560921134"
EMBED_THUMB = "https://i.imgur.com/nBQbe9R.png"
EMBED_WARNING = "**⚠️ Caution**: Distressing content; reader discretion is advised."

# TODO: Use bot.session
async def url_to_soup(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            text = await response.text()
            return BeautifulSoup(text, 'html.parser')


class ForumThread:

    def __init__(self, node_id):
        self.url = f'{PATCH_NOTES_URL}/{node_id}'
        self.page = None

    async def build(self):
        self.page = await url_to_soup(self.url)
        # self.page = await url_to_soup(self.url)

    @property
    def title(self):
        return self.page.find('h2', {'class': 'b-post__title js-post-title OLD__post-title'}).text.strip()

    @property
    def body(self):
        content = self.page.find('div', {'class': re.compile('.*post-content.*')}).text.strip()
        return content[:600] + (content[600:] and '..')


async def fetch_thread_list(url: str):
    forum = await url_to_soup(url)

    threads = []
    for thread in forum.find_all('tr', {'data-node-id': True}):
        threads.append(thread['data-node-id'])

    threads.sort(reverse=True)
    return threads


class CombatArmsUpdates(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.check_for_updates.start()
        self.cache = []

    def cog_unload(self):
        self.check_for_updates.cancel()

    @tasks.loop(minutes=10)
    async def check_for_updates(self):
        new_cache = await fetch_thread_list(PATCH_NOTES_URL)

        if self.cache:
            for i in new_cache:
                if i in self.cache:
                    break

                thread = ForumThread(i)
                await thread.build()
                await self.announce_update(thread)

        self.cache = new_cache

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    async def announce_update(self, item):
        channel = self.bot.get_channel(self.bot.cfg['game_updates_channel'])

        update = discord.Embed(title=item.title, description=item.body, color=0xff9922, url=item.url)
        update.set_author(name="Combat Arms: Reloaded")
        update.set_thumbnail(url=EMBED_THUMB)
        update.set_image(url=EMBED_BANNER)
        await channel.send(embed=update)

        update_warning = discord.Embed(description=EMBED_WARNING, color=0xff6600)
        await channel.send(embed=update_warning)


def setup(bot):
    bot.add_cog(CombatArmsUpdates(bot))
