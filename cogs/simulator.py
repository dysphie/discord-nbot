import zlib
from io import StringIO

from discord import TextChannel, User
from discord.ext import commands
from markovify import NewlineText
from motor import motor_asyncio

from cogs import utils

MAX_NAME_LENGTH = 32

class Parrot(commands.Cog, name="Parrot"):

    def __init__(self, bot):
        self.bot = bot
        self.models = bot.db['markov_models']
        self.history = bot.db['chat_archive']

    @commands.command(aliases=["b", "be", "imp"])
    async def parrot(self, ctx, name):

        user = utils.lazyfind_user(ctx.guild, name)
        if not user:
            return

        model = await self.fetch_user_model(user.id)
        if not model:
            await ctx.send(f'Generating speech model for {user.display_name}..')
            model = await self.create_model_for_user(user.id)
            if not model:
                await ctx.send('Apologies but something is fucked')
                return

        for i in range(3):
            sentence = model.make_sentence(tries=100)
            if sentence:
                await self.parrot_user(user, ctx.channel, sentence)

    async def fetch_user_model(self, user_id: int):
        result = await self.models.find_one({'_id': user_id}, {'msg': 1})
        if result:
            return NewlineText.from_json(zlib.decompress(result['msg']))

    async def save_user_model(self, user_id: int, model):
        packed_model = zlib.compress(model.to_json().encode('utf-8'), level=9)
        await self.models.update_one(
            {'_id': user_id},
            {'$set': {'msg': packed_model}},
            upsert=True)

    async def create_model_for_user(self, user_id: int):
        results = self.history.find({'author': user_id}, {'msg': 1})

        f = StringIO()
        async for doc in results:
            f.write(doc['msg'])
            f.write('\n')

        model = NewlineText(f.getvalue(), well_formed=False)
        if model:
            await self.save_user_model(user_id, model)
            return model

    @staticmethod
    async def create_corpus_from_message_history(messages: motor_asyncio.AsyncIOMotorCursor):
        f = StringIO()
        async for doc in messages:
            f.write(doc['msg'])
            f.write('\n')
        return f.getvalue()

    async def parrot_user(self, user: User, channel: TextChannel, content: str):
        utils_cog = self.bot.get_cog('Utils')
        if not utils_cog:
            return

        webhook = await utils_cog.get_webhook_for_channel(channel)
        if not webhook:
            return

        suffix = ' Simulator'
        maxlen = MAX_NAME_LENGTH - len(suffix)
        username = utils.truncate_string(user.display_name, maxlen) + suffix

        await webhook.send(username=username, content=content, avatar_url=user.avatar_url)


def setup(bot):
    bot.add_cog(Parrot(bot))
