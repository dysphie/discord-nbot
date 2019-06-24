import discord
from discord.ext import commands
import motor.motor_asyncio
import utils


DB_URI = 'mongodb+srv://nbot:VzjRF00xYnZlkRvg@cluster0-zqoze.mongodb.net/test?retryWrites=true'


class DiscordBot(commands.Bot):

    def __init__(self):
        self.startup_extensions = ['cogs.simulator', 'cogs.conversation', 'cogs.colors', 'cogs.highlighter']
        self.db = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)['nbot']
        super().__init__(command_prefix=commands.when_mentioned_or("?"))

    def run(self):
        for ext in self.startup_extensions:
            try:
                self.load_extension(ext)
            except Exception as e:
                print(f'Failed to load extension {ext}: {e}')
        super().run('NDAwMDkyNDA5ODM0NTA0MjEy.XRAi-w.enrnFiZIKOE7Yq3YatMCOINUDok', reconnect=True)

if __name__ == "__main__":
    DiscordBot().run()
