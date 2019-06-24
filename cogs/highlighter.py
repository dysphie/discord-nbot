import discord
from discord.ext import commands
from collections import defaultdict


class Highlighter(commands.Cog):
    ''' DMs you when certain words are said in certain channels.'''

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db['highlights']
        self.cache = defaultdict(list)

    # Memory heavy, okay for now?
    async def populate_cache(self):
        async for document in self.db.find():
            user = document['_id']
            for keyphrase in document['keyphrases']:
                self.cache[user].append(keyphrase)

    @commands.command()
    async def highlight(self, ctx, *, keyphrase: str):

        user_id = ctx.message.author.id
        self.cache[user_id].append(keyphrase)

        result = await self.db.update_one({'_id': user_id}, {'$set': {'keyphrases': self.cache[user_id]}}, upsert=True)
        print(f'Will notify {ctx.message.author.name} when anything in here is said: \n {self.cache[user_id]}')

    @commands.Cog.listener()
    async def on_message(self, message):
        for user_id, keyphrases in self.cache.items():
            for keyphrase in keyphrases:
                if keyphrase.lower() in message.content.lower():
                    user = self.bot.get_user(user_id)
                    print(f'I should notify {user.name} that {message.author.name} sent {keyphrase}')


def setup(bot):
    cog = Highlighter(bot)
    bot.loop.create_task(cog.populate_cache())
    bot.add_cog(cog)
