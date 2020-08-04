# TODO:
#   Automatically regenerate models after a while
#   Automatically save user messages
#   Better webhook username suffix logic
#   Move impersonate function to utils cog for DRY
import zlib

import discord
import markovify
from discord.ext import commands
from discord.utils import find, escape_mentions
from io import StringIO

INVISIBLE_CHAR = '\u17B5'
MAX_NAME_LENGTH = 32


class DiscordText(markovify.NewlineText):
    # github.com/jsvine/markovify/issues/84
    def test_sentence_input(self, sentence):
        return True


class Markov(commands.Cog, name="Markovify"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.history = bot.db['chat_archive']
        self.models = bot.db['markov.models']

    @commands.command()
    async def be(self, ctx, name):

        user = None
        if not name:
            user = ctx.user
        else:
            for m in ctx.guild.members:
                if name.lower() in [n.lower() for n in [m.name, m.display_name]]:
                    user = m

        if not user:
            await ctx.send('User not found')
            return

        model = await self.get_user_speech_model(user.id)
        if model:
            for i in range(3):
                content = escape_mentions(model.make_sentence(tries=100))
                content and await self.simulate_user(user, content, ctx.message.channel)

    async def get_user_speech_model(self, uid: int) -> DiscordText:
        model = await self.models.find_one({'_id': uid})
        if model:
            model = DiscordText.from_json(zlib.decompress(model['m']))
        else:
            model = await self.create_user_speech_model(uid)
        return model

    async def create_user_speech_model(self, uid: int):
        messages = self.history.find({'a': uid}, {'m': 1, '_id': 0})
        if messages:
            corpus = await self.create_corpus_from_message_history(messages)
            if corpus:
                model = DiscordText(corpus)
                await self.store_user_speech_model(model, uid)
                return model

    async def store_user_speech_model(self, model, uid: int):
        packed_model = zlib.compress(model.to_json().encode('utf-8'), level=9)
        await self.models.update_one(
            {'_id': uid},
            {'$set': {'m': packed_model}},
            upsert=True)

    @staticmethod
    async def create_corpus_from_message_history(messages):
        f = StringIO()
        async for doc in messages:
            f.write(doc['m'])
            f.write('\n')
        return f.getvalue()

    async def simulate_user(self, member: discord.Member, content: str, channel: discord.TextChannel):
        utils = self.bot.get_cog('Utils')
        if not utils:
            return

        suffix = ' Simulator'
        maxlen = MAX_NAME_LENGTH - len(suffix)
        username = utils.truncate_string(member.display_name, maxlen) + suffix

        webhook = await utils.get_webhook_for_channel(channel)
        if webhook:
            await webhook.send(
                username=username,
                content=content,
                avatar_url=member.avatar_url)


def setup(bot):
    bot.add_cog(Markov(bot))
