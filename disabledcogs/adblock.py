from discord.ext import commands


class Adblock(commands.Cog, name="Adblock"):
    """Reposts PatchBot updates without sponsored messages"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot and message.author.name == 'PatchBot':
            for embed in message.embeds:
                if "This update is brought to you by" not in embed.author.name:
                    await message.channel.send(embed=embed)
            await message.delete()


def setup(bot):
    bot.add_cog(Adblock(bot))
