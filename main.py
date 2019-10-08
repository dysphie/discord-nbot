from discord.ext import commands
import motor.motor_asyncio
import os
import yaml


class DiscordBot(commands.Bot):

    def __init__(self):

        try:
            self.token = os.environ['NBOT_TOKEN']
            self.db_uri = os.environ['NBOT_DB_URI']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

        self.exts = ['cogs.colors', 'cogs.cleverbot', 'cogs.yeller', 'cogs.ffz',
                     'cogs.weather', 'cogs.adblock', 'cogs.admin',
                     'cogs.ca-updates', 'cogs.paraphraser']
        self.db = motor.motor_asyncio.AsyncIOMotorClient(self.db_uri)['nbot']
        self.cfg = yaml.safe_load(open('config.yml'))
        super().__init__(command_prefix=commands.when_mentioned_or("."))

    def run(self):
        for ext in self.exts:
            # try:
            self.load_extension(ext)
            # except Exception as e:
            # print(f'Failed to load extension {ext}: {e}')
        super().run(self.token, reconnect=True)

    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as:')
        print(bot.user.name)
        print(bot.user.id)
        print('-------------------')


if __name__ == "__main__":
    DiscordBot().run()
