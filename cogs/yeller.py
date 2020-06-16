from discord.ext import commands


class Yeller(commands.Cog, name="Yeller"):

    def __init__(self, bot):
        self.bot = bot
        self.yells = self.bot.db['yells']

    async def get_yell(self):
        pipeline = [{'$sample': {'size': 1}}]
        async for doc in self.yells.aggregate(pipeline):
            return doc['m']

    async def save_yell(self, message: str):
        document = {'m': message}
        await self.yells.insert_one(document)

    @staticmethod
    def is_message_yell(message: str):
        alph = list(filter(str.isalpha, message))
        percentage = sum(map(str.isupper, alph)) / len(alph)
        return percentage > 0.85 and len(message.split()) > 2

    @commands.Cog.listener()
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def on_message(self, message):

        if message.author.bot:
            return

        text = message.clean_content
        if not text:
            return

        if self.is_message_yell(text):
            async with message.channel.typing():
                response = await self.get_yell()
                if response:
                    await message.channel.send(response)
                await self.save_yell(text)


def setup(bot):
    bot.add_cog(Yeller(bot))
