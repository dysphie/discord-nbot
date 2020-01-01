import discord
import motor.motor_asyncio
import yaml
from discord.ext import commands
from os import listdir, environ
from os.path import isfile, join


class DiscordBot(commands.Bot):

    def __init__(self):

        try:
            self.token = environ['NBOT_TOKEN']
            self.db_uri = environ['NBOT_DB_URI']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

        self.db = motor.motor_asyncio.AsyncIOMotorClient(self.db_uri)['nbot']
        self.cfg = yaml.safe_load(open('config.yml'))
        super().__init__(command_prefix=commands.when_mentioned_or(self.cfg['bot-prefix']))

    def run(self):
        cogs_dir = 'cogs'
        for extension in [f.replace('.py', '') for f in listdir(cogs_dir) if isfile(join(cogs_dir, f))]:
            try:
                self.load_extension(cogs_dir + "." + extension)
            except (discord.ClientException, ModuleNotFoundError):
                print(f'Failed to load extension {extension}.')
                traceback.print_exc()
        super().run(self.token, reconnect=True)

    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as:')
        print(self.user.name)
        print(self.user.id)
        print('-------------------')


if __name__ == "__main__":
    DiscordBot().run()
