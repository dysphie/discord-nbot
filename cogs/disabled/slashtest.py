from discord import slash_command, ApplicationContext, Member
from discord.ext import commands

from main import DiscordBot


class SlashTest(commands.Cog):

    def __init__(self, bot):
        self.bot: DiscordBot = bot

    @slash_command(name="testslash",
                   description="Test slash command",
                   guild_ids=[759525750201909319])
    async def testslash(self, ctx: ApplicationContext):
        pass


def setup(bot):
    bot.add_cog(SlashTest(bot))
