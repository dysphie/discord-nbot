import discord
from utils import clean
from discord.ext import commands
from timeit import default_timer as timer


class Yeller(commands.Cog, name="Yeller"):

    def __init__(self, bot):
        self.bot = bot
        self.yells = self.bot.db['yells']

    @commands.Cog.listener()
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def on_message(self, message):

        if(message.author.bot):
            return

        text = clean(message.content)
        if await self.is_yell(text):
            async with message.channel.typing():
                await self.save_yell(text)
                response = clean(await self.get_yell())
                if response:
                    await message.channel.send(response)

    async def get_yell(self):
        pipeline = [{'$sample': {'size': 1}}]
        async for doc in self.yells.aggregate(pipeline):
            return doc['m']

    async def save_yell(self, message: str):
        document = {'m': message}
        await self.yells.insert_one(document)

    async def is_yell(self, message: str):
        alpha = list(filter(str.isalpha, message))
        percentage = sum(map(str.isupper, alpha)) / len(alpha)
        return (percentage > .85 and len(message) > 12)


def setup(bot):
    bot.add_cog(Yeller(bot))
