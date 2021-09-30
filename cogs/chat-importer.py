from typing import List

import discord
from discord.ext import tasks, commands


class ChatArchiver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitored_channels = self.bot.cfg['monitored_channels']
        self.archive = bot.db['chat_archive']
        self.archive_stuff.start()

    def cog_unload(self):
        self.archive_stuff.cancel()

    @tasks.loop(hours=48)
    async def archive_stuff(self):
        for channel_id in self.monitored_channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.archive_channel(channel)

    async def archive_channel(self, channel: discord.TextChannel):
        # print(f'Archiving channel #{channel.name}...')

        after = None

        pipeline = [
            {'$match': {'channel': channel.id}},
            {'$sort': {'date': -1}},
            {'$limit': 1},
        ]

        async for doc in self.archive.aggregate(pipeline):
            after = doc['date']
            break

        count = 0
        to_save = []
        try:
            async for msg in channel.history(limit=None, after=after):
                to_save.append({
                    '_id': msg.id,
                    'author': msg.author.id,
                    'channel': msg.channel.id,
                    'date': msg.created_at,
                    'msg': msg.content,
                })

                if len(to_save) == 500:
                    count += await self._insert_many(to_save)
                    to_save = []

            if to_save:
                count += await self._insert_many(to_save)

            if count > 0:
                print(f'Saved {count} messages from #{channel.name}')

        except Exception as e:
            print(f'Something went wrong archiving #{channel.name}: {e}')

    async def _insert_many(self, documents: List[dict]) -> int:
        result = await self.archive.insert_many(documents)
        return len(result.inserted_ids)

    @archive_stuff.before_loop
    async def before_archive(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(ChatArchiver(bot))
