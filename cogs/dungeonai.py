import aiohttp
import asyncio
import discord
from discord.ext import commands


ACCESS_TOKEN = 'cd9f46d0-2c68-11ea-b356-4182da402b1c'
API_URL = 'https://api.aidungeon.io'

class DungeonAI(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.task = self.bot.loop.create_task(self.initialize())
        self.prompt_id = None

    async def initialize(self):
        self.session = aiohttp.ClientSession()
    
    def cog_unload(self):
        self.task.cancel()
        self.session.close()
    
    @commands.command()
    async def prompt(self, ctx, *, prompt: str):

        url = f'{API_URL}/sessions'

        headers = {
            'x-access-token': ACCESS_TOKEN
        }

        payload = {
            "storyMode": "custom",
            "characterType": None,
            "name": None,
            "customPrompt": prompt,
            "promptId": None
        }

        async with self.session.post(url, headers=headers, data=payload) as r:
            json = await r.json()
            self.prompt_id = json['id']
            story = json['story'][0]['value']
            if story:
                await ctx.send(story)

    @commands.command()
    async def rp(self, ctx, *, message: str):

        if not self.prompt_id:
            await ctx.invoke(bot.get_command("prompt"))
            return

        url = f'{API_URL}/sessions/{self.prompt_id}/inputs'
        headers = {'x-access-token': ACCESS_TOKEN}
        payload = {'text': message}

        async with self.session.post(url, headers=headers, data=payload) as r:
            json = await r.json()
            story = json[-1].get('value')
            if story:
                await ctx.send(story)


def setup(bot):
    bot.add_cog(DungeonAI(bot))



