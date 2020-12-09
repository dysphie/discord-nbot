import logging
from datetime import datetime
import discord
from discord.ext import tasks, commands


class EmoteCacheUpdater(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.data = bot.db['newporter.emotes']
        self.logs = bot.db['newporter.logs']  # Needed to check when the emote cache was last updated
        self.stats = bot.db['newporter.stats']  # Needed to fetch the most used emotes
        self.guild = None  # Guild we are using as the emote cache
        self.check_for_updates.start()

    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])

    async def get_last_update_time(self):
        result = await self.logs.find_one({'_id': 'lastCacheUpdate'})
        if result:
            return result['date']

    @tasks.loop(hours=2)
    async def check_for_updates(self):
        last_update_time = await self.get_last_update_time()
        if not last_update_time or (datetime.now() - last_update_time).seconds/3600 > 2:
            await self.update()

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    async def update(self):

        #  TODO: Better sanity checks. $lookup instead of 2 queries
        top_used = set()
        cursor = self.stats.find({'uses': {'$gt': 0}})
        cursor.sort('uses', -1).limit(40)
        async for doc in cursor:
            top_used.add(doc['_id'])

        for emote in self.guild.emojis:
            await emote.delete()

        num_uploaded = 0
        async for doc in self.data.find({'_id': {'$in': list(top_used)}}):
            async with self.session.get(doc['url']) as response:
                if response.status == 200:
                    image = await response.read()
                    try:
                        await self.guild.create_custom_emoji(name=doc['name'], image=image)
                    except discord.HTTPException:
                        pass
                    finally:
                        num_uploaded += 1

        print(f'EmoteCacheUpdater: Caching complete. Uploaded: {num_uploaded}')
        await self.logs.update_one({'_id': 'lastCacheUpdate'}, {'$set': {'date': datetime.now()}}, upsert=True)
        return num_uploaded


def setup(bot):
    bot.add_cog(EmoteCacheUpdater(bot))
