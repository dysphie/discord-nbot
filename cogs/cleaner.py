from datetime import date, datetime, timedelta
from discord.ext import tasks, commands

class Cleaner(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.channel_ids = [359821217915469825, 559661355133829141]
        self.cleaner.start()

    def cog_unload(self):
        self.cleaner.cancel()

    @tasks.loop(hours=12)
    async def cleaner(self):
        yday = datetime.utcnow() - timedelta(days=1)

        for channel_id in self.channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.purge(before=yday, oldest_first=True)

    @cleaner.before_loop
    async def before_cleaner(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Cleaner(bot))
