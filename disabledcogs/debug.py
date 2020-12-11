import asyncio
from time import time
from typing import Optional
from aiohttp import ClientSession
from discord import Guild
from discord.ext import commands
from discord.ext.commands import Bot

TEST_URL = 'https://cdn.frankerfacez.com/emoticon/392904/2'


class Debug(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        self.session: ClientSession = getattr(bot, 'session', ClientSession(loop=bot.loop))
        self.emote_guild: Optional[Guild] = None
        self.emotes = {
            'test': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test2': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test3': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test4': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test5': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test6': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test7': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test8': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x',
            'test9': 'https://cdn.betterttv.net/emote/5a6edb51f730010d194bdd46/2x'
        }

    @commands.Cog.listener()
    async def on_ready(self):
        self.emote_guild = self.bot.get_guild(719448049981849620)

    async def upload_emote_by_url(self, name, url, replacements):
        async with self.session.get(url) as r:
            image_bytes = await r.read()
            emote = await self.emote_guild.create_custom_emoji(name=name, image=image_bytes)
            replacements[name] = emote

    @commands.command()
    async def debug(self, ctx):

        start = time()
        await self.func2()
        print("--- %.8f seconds ---" % (time() - start))

    async def func1(self):
        for name, url in self.emotes.items():  # dict
            await self.upload_emote_by_url(name, url)  # wrapper to create_custom_emoji

    async def func2(self):
        msg = 'Hello $peepoHappy $peepoFat $peepoObese'
        prefixed_words = ['peepoHappy', 'peepoFat', 'peepoObese']

        replacements = {}

        emote_uploading_tasks = [
            asyncio.create_task(self.upload_emote_by_url(name, url, replacements))
            for name, url in self.emotes.items()
        ]

        await asyncio.gather(*emote_uploading_tasks)
        for word in prefixed_words:
            emote = replacements.get(word)
            msg = msg.replace(word, str(emote))

        print(f'Done => {msg}')
        # asyncio.create_task(message.delete())
        asyncio.create_task(emote.delete() for emote in replacements.values())


def setup(bot):
    bot.add_cog(Debug(bot))
