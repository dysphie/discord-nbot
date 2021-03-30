import aiohttp
import discord
import motor.motor_asyncio
import yaml
from discord.ext import commands
from os import environ
import sys
import traceback
from pathlib import Path
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import remove_all_commands

intents = discord.Intents.default()
intents.members = True


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


class DiscordBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix='.',
            intents=intents,
            allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False)
        )

        self.db = motor.motor_asyncio.AsyncIOMotorClient(environ['NBOT_DB_URI'])['nbot']
        self.cfg = yaml.safe_load(open('config.yml'))
        self.session = aiohttp.ClientSession(loop=self.loop)

    def cog_unload(self):
        self.session.close()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Logged in as {self.user.name} (ID: {self.user.id})')

        # await remove_all_commands(self.user.id, environ['NBOT_TOKEN'], [719448049981849620])

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
        for file in Path('cogs').glob('**/*.py'):
            *tree, _ = file.parts
            try:
                self.load_extension(f"{'.'.join(tree)}.{file.stem}")
            except Exception as e:
                traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
            else:
                print(f'Loaded extension {file.stem}')


if __name__ == "__main__":
    bot = DiscordBot()
    slash = SlashCommand(bot, sync_commands=True)
    bot.load_extensions()
    bot.run(environ['NBOT_TOKEN'], reconnect=True)
