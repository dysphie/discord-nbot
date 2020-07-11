import aiohttp
import motor.motor_asyncio
import yaml
from discord import Game
from discord.ext import commands
from os import environ
import sys
import traceback
from pathlib import Path


class CustomContext(commands.Context):  # TODO
    pass


class DiscordBot(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix='.')
        self.db = motor.motor_asyncio.AsyncIOMotorClient(environ['NBOT_DB_URI'])['nbot']
        self.cfg = yaml.safe_load(open('config.yml'))
        self.task = self.loop.create_task(self.__ainit__())

    async def __ainit__(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_extensions()

    def cog_unload(self):
        self.task.cancel()
        self.session.close()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Logged in as {self.user.name} (ID: {self.user.id})')
        await self.change_presence(activity=Game(name="Red Canyon"))

    async def get_context(self, message, *, cls=CustomContext):
        return await super().get_context(message, cls=cls)

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
    DiscordBot().run(environ['NBOT_TOKEN'])
