# TODO:
#   Automatically regenerate models after a while
#   Automatically save user messages
#   Better webhook username suffix logic
#   Move impersonate function to utils cog for DRY
import zlib

import aiohttp
import discord
import markovify
from discord.ext import commands
from discord.utils import find, escape_mentions
from io import StringIO
from discord import Webhook, AsyncWebhookAdapter

INVISIBLE_CHAR = '\u17B5'


class DiscordText(markovify.NewlineText):
    # github.com/jsvine/markovify/issues/84
    def test_sentence_input(self, sentence):
        return True


class Markov(commands.Cog, name="Markovify"):

    def __init__(self, bot):
        self.bot = bot
        self.task = self.bot.loop.create_task(self.initialize())
        self.history  = bot.db['chat_archive']
        self.models   = bot.db['markov.models']
        self.webhooks = bot.db['webhooks']

    async def initialize(self):
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.task.cancel()
        self.session.close()

    @commands.command()
    async def be(self, ctx, name):
        user = find(lambda m: name in [m.name, m.display_name], ctx.guild.members)
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
            {'$set': {'m': packed_model }},
            upsert=True)

    async def create_corpus_from_message_history(self, messages):
        f = StringIO()
        async for doc in messages:
            f.write(doc['m'])
            f.write('\n')
        return f.getvalue()


    async def simulate_user(self, member: discord.Member, message: str, channel: discord.TextChannel):

        username = member.name[:20] + (member.name[20:] and ' ..') + ' Simulator'

        webhook = await self.get_webhook_for_channel(channel)
        await webhook.send(
            username=username,
            content=message,
            avatar_url=member.avatar_url
        )


    async def get_webhook_for_channel(self, channel):
        data = await self.webhooks.find_one({'_id': channel.id})
        if not data:
            webhook = await channel.create_webhook(name='test')
            data = { '_id': channel.id, 'wid': webhook.id, 'token': webhook.token }
            await self.webhooks.insert_one(data)

        webhook = Webhook.partial(data['wid'], data['token'], adapter=AsyncWebhookAdapter(self.session))
        return webhook



def setup(bot):
    bot.add_cog(Markov(bot))
