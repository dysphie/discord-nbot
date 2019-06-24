import discord
from discord.ext import commands
from io import StringIO
import markovify
from datetime import datetime


class DiscordText(markovify.NewlineText):
    # github.com/jsvine/markovify/issues/84

    def test_sentence_input(self, sentence):
        return True


class Simulator(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.models = bot.db['model_cache']
        self.chat = bot.db['chat_archive']

    @commands.command(aliases=['bharsh', 'be'])
    async def imitate(self, ctx, *, username):
        member = ctx.channel.guild.get_member_named(username)
        if not member:
            print(f'User `{username}` not found.')
            return

        model = await self.get_speech_model(member.id)
        if not model:
            print('Could not create speech model for user.')
            return

        for i in range(3):
            message = model.make_sentence()
            await ctx.send(message)

    async def get_speech_model(self, user_id):
        # model = await self.models.find_one({'_id': user_id})
        # if not model:
        model = await self.create_speech_model(user_id)
        print('post create_speech_model')
        return model

    async def create_speech_model(self, user_id):
        print('create_speech_model()')
        f = StringIO()
        messages = self.chat.find({'a': user_id}, {'m': 1, '_id': 0})
        print(type(messages))

        async for message in messages:
            f.write(message['m'])
            f.write('\n')
        corpora = f.getvalue()

        model = DiscordText(corpora)

        await self.models.update_one({
            '_id': user_id},
            {'$set': {'model': model, 'date': datetime.utcnow()}},
            upsert=True)

        return model


def setup(bot):
    bot.add_cog(Simulator(bot))
