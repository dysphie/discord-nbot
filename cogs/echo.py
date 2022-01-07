from discord import slash_command, ApplicationContext
from discord.ext import commands


class Echo(commands.Cog, name="Echo"):

    def __init__(self, bot):
        self.bot = bot

    @commands.is_owner()
    @commands.command()
    async def echo(self, ctx, channel_id, msg):
        channel = await self.bot.fetch_channel(channel_id)
        if channel:
            await channel.send(msg)
        else:
            await ctx.send('Channel not found')


def setup(bot):
    bot.add_cog(Echo(bot))
