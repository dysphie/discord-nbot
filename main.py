import logging
import os
from abc import ABC
import aiohttp
import motor.motor_asyncio
import yaml
from discord.ext import commands
from os import environ
import sys
import traceback
from pathlib import Path
import discord


class CustomContext(commands.Context):

    async def error(self, content):
        embed = discord.Embed(color=0xf05840, description=f'❌ {content}')
        await self.send(embed=embed)

    async def warning(self, content):
        embed = discord.Embed(color=0xffcb05, description=f'⚠️ {content}')
        await self.send(embed=embed)

    async def success(self, content):
        embed = discord.Embed(color=0x8cc63e, description=f'✅ {content}')
        await self.send(embed=embed)

    async def info(self, content):
        embed = discord.Embed(color=0x41c8f5, description=f'ℹ️ {content}')
        await self.send(embed=embed)


class DiscordBot(commands.Bot, ABC):

    def __init__(self):
        super().__init__(
            command_prefix='.',
            allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False),
            intents=discord.Intents.all()
        )

        self.logger = None
        self.init_logger()
        self.db = motor.motor_asyncio.AsyncIOMotorClient(environ['NBOT_DB_URI'])['nbot']
        self.cfg = yaml.safe_load(open('config.yml'))
        self.session = aiohttp.ClientSession(loop=self.loop)

    def init_logger(self):
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        self.logger.addHandler(handler)

    def cog_unload(self):
        self.session.close()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Logged in as {self.user.name} (ID: {self.user.id})')

    async def get_context(self, message, *, cls=CustomContext):
        return await super().get_context(message, cls=cls)

    async def on_command_error(self, ctx, error):
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        await self.process_commands(message)

    def load_extensions(self):
        exts = os.listdir('./cogs')
        for ext_name in exts:
            if ext_name.endswith('.py'):
                try:
                    self.load_extension(f'cogs.{ext_name[:-3]}')
                except Exception as e:
                    print(e)
                else:
                    print(f'Loaded extension: {ext_name[:-3]}')


if __name__ == "__main__":
    bot = DiscordBot()
    bot.load_extensions()
    bot.run(environ['NBOT_TOKEN'], reconnect=True)
