from aiogoogletrans import Translator
from discord import HTTPException
from discord.ext import commands


class Translation(commands.Cog, name="Translator"):

    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command(aliases=["trans", "t", "what"])
    async def translate(self, ctx, *, message):
        if ctx.author.bot:
            return

        result = await self.translator.translate(message)
        try:
            await ctx.send(result.text)
        except HTTPException:
            pass


def setup(bot):
    bot.add_cog(Translation(bot))
