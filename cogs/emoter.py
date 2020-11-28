import asyncio
import logging
import re
from abc import abstractmethod
from datetime import datetime
import discord
import pymongo
from discord.ext import commands, tasks
from pymongo.errors import BulkWriteError
from abc import ABCMeta

EMOTE_PATTERN = re.compile(r'\$([^\s$]+)')
INVISIBLE_CHAR = '\u17B5'


class EmoteAPIManager(metaclass=ABCMeta):

    @abstractmethod
    def __init__(self, session, storage):
        self.session = session
        self.storage = storage

    @abstractmethod
    async def backup_locally(self):
        pass


class BTTVManager(EmoteAPIManager):

    def __init__(self, session, storage):
        super().__init__(session, storage)

    id = "bttv"
    url = 'https://api.betterttv.net/3/emotes/shared/top'
    params = {'offset': 0, 'limit': 100}

    async def backup_locally(self):

        print(f'[{self.id}] Backing up emotes')

        # TODO: Backup in case the import fails

        try:
            deleted = await self.storage.delete_many({'source': 'bttv'})
        except Exception as e:
            print(e)
        else:
            print(f'[{self.id}] Deleted {deleted.deleted_count} existing emotes')

        for i in range(0, 200):

            emotes = []

            self.params['offset'] = i * 100
            async with self.session.get(self.url, params=self.params) as r:
                if r.status != 200:
                    raise Exception(f'[{self.id}] API responded with status {r.status}')

                data = await r.json()

                for e in data:
                    name = e['emote']['code']
                    file = e['emote']['id']

                    emote = {
                        'name': name,
                        'owner': 0,
                        'url': f'https://cdn.betterttv.net/emote/{file}/2x',
                        'source': 'bttv'
                    }

                    emotes.append(emote)

                num_inserted = 0
                try:
                    # TODO: 'ordered=False' might lead to the wrong emote being
                    #  added if a name exists twice in 'emotes', but setting it
                    #  to false halts the entire bulk write
                    result = await self.storage.insert_many(emotes, ordered=False)
                except BulkWriteError as bwe:
                    num_inserted = bwe.details['nInserted']
                else:
                    num_inserted = len(result.inserted_ids)
                finally:
                    print(f'[{self.id}] Page {i}: Inserted {num_inserted} emotes')

        print(f'[{self.id}] Finished import')


class FFZManager(EmoteAPIManager):
    id = 'ffz'
    url = 'https://api.frankerfacez.com/v1/emoticons'
    params = {
        'high_dpi': 'off',
        'sort': 'count-desc',
        'per_page': 200,
        'page': 1
    }

    def __init__(self, session, storage):
        super().__init__(session, storage)

    async def backup_locally(self):

        try:
            deleted = await self.storage.delete_many({'source': 'ffz'})
        except Exception as e:
            print(e)
        else:
            print(f'[{self.id}] Deleted {deleted.deleted_count} existing emotes')

        print(f'[{self.id}] Backing up emotes')
        await self.backup_from_page(1)
        print(f'[{self.id}] Finished import')

    async def backup_from_page(self, page_num: int):

        self.params['page'] = page_num  # Update request headers

        async with self.session.get(self.url, params=self.params) as r:
            if r.status != 200:
                raise Exception(f'[{self.id}] API responded with status {r.status}')

            data = await r.json()

            emotes = []
            for e in data['emoticons']:
                name = e['name']
                url = e['urls'].get('2') or e['urls'].get('1')

                emote = {
                    'name': name,
                    'owner': 0,
                    'url': f'https:{url}',
                    'source': 'ffz'
                }

                emotes.append(emote)

            num_inserted = 0
            try:
                # TODO: 'ordered=False' might lead to the wrong emote being
                #  added if a name exists twice in 'emotes', but setting it
                #  to false halts the entire bulk write
                result = await self.storage.insert_many(emotes, ordered=False)
            except BulkWriteError as bwe:
                num_inserted = bwe.details['nInserted']
            else:
                num_inserted = len(result.inserted_ids)
            finally:
                print(f'[{self.id}] Page {self.params["page"]}: Inserted {num_inserted} emotes')

            # Recursively fetch subsequent pages
            # if data['_pages'] > page_num:
            if page_num < 200:  # TODO: Softcode. limit of 200 for now
                await self.backup_from_page(page_num + 1)


class EmoteCacheUpdater:

    def __init__(self, logs, stats, guild, data, session):
        self.data = data
        self.session = session
        self.logs = logs  # Needed to check when the emote cache was last updated
        self.stats = stats  # Needed to fetch the most used emotes
        self.guild = guild  # Guild we are using as the emote cache

    async def check_for_updates(self):

        result = await self.logs.find_one({'_id': 'lastCacheUpdate'})
        if result and (datetime.now() - result['date']).days < 2:
            print('EmoteCacheUpdater: No update needed')
            return

        await self.update()

    async def update(self):

        pipeline = [
            {"$match": {'uses': {'$gt': 1}}},
            {"$sort": {"uses": 1}},
            {"$project": {"name": 1}},
            {"$limit": 40},
        ]

        # TODO: Combine both queries into one with aggregate?
        most_used = []
        async for doc in self.stats.aggregate(pipeline):
            most_used.append(doc['_id'])

        if not most_used:
            logging.warning('Database returned no data for most used emotes')
            return
        else:
            print(most_used)

        for emote in self.guild.emojis:
            await emote.delete()

        async for doc in self.data.find({'name': {'$in': most_used}}):  # TODO: Limit results
            async with self.session.get(doc['url']) as response:
                if response.status == 200:

                    print(f'Caching most used emotes: {doc}')
                    image = await response.read()
                    await self.guild.create_custom_emoji(name=doc['name'], image=image)

        await self.logs.update_one({'_id': 'lastCacheUpdate'}, {'$set': {'date': datetime.now()}}, upsert=True)


class EmoteCollectionUpdater:

    def __init__(self, logs, emotes, session):
        self.session = session
        self.logs = logs
        self.emotes = emotes

        bttv = BTTVManager(self.session, self.emotes)
        ffz = FFZManager(self.session, self.emotes)
        self.workers = [bttv, ffz]

    async def check_for_updates(self):
        result = await self.logs.find_one({'_id': 'lastEmoteCollectionUpdate'})
        if result and (datetime.now() - result['date']).days < 7:
            print('EmoteCollectionUpdater: No update needed')
            return

        await self.update()

    async def update(self):
        await self.emotes.create_index([("name", pymongo.DESCENDING)], unique=True)
        for worker in self.workers:
            await worker.backup_locally()
        # TODO: Confirm it was successful

        await self.logs.update_one({'_id': 'lastEmoteCollectionUpdate'}, {'$set': {'date': datetime.now()}}, upsert=True)


class Emoter(commands.Cog):

    def __init__(self, bot):
        self.logs = bot.db['emoter.logs']
        self.emotes = bot.db['emoter.emotes']
        self.stats = bot.db['emoter.stats']
        self.session = bot.session
        self.emote_guild = None

        self.cache_updater = None
        self.emotes_updater = EmoteCollectionUpdater(self.logs, self.emotes, self.session)

        self.bot = bot
        self.updater.start()

    def cog_unload(self):
        self.updater.cancel()

    @tasks.loop(hours=2)
    async def updater(self):
        await self.emotes_updater.check_for_updates()
        await self.cache_updater.check_for_updates()

    @updater.before_loop
    async def before_cleaner(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        self.emote_guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])
        self.cache_updater = EmoteCacheUpdater(self.logs, self.stats, self.emote_guild, self.emotes, self.session)

    async def upload_emote_from_url(self, guild, name, url):
        async with self.bot.session.get(url) as response:
            if response.status != 200:
                raise discord.HTTPException(response.status, 'Invalid image URL')

            image_bytes = await response.read()
            emote = await guild.create_custom_emoji(name=name, image=image_bytes)
            return emote

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        emotes_used = []

        #  Find all potential emotes (e.g. $duck)
        prefixed_words = list(set(EMOTE_PATTERN.findall(message.content)))
        if not prefixed_words:
            return

        # Avoid replacing $duck for <:duck:123> before replacing $ducks
        prefixed_words.sort(key=len)

        if not self.emote_guild:
            print('Emoter: Cache is null.')
        else:
            for i, word in enumerate(prefixed_words):
                # Find emote in local guild
                emote = discord.utils.find(lambda m: m.name == word, self.emote_guild.emojis)
                if not emote:
                    # Give up for now
                    continue

                print('replaced locally')
                message.content = message.content.replace(f'${word}', str(emote))
                emotes_used.append(word)
                del prefixed_words[i]

        delete_queue = [message]

        # Find remaining emotes in database
        if prefixed_words:
            async for emote in self.emotes.find({'name': {'$in': prefixed_words}}):
                name = emote['name']
                try:
                    emote = await self.upload_emote_from_url(message.channel.guild, name, emote['url'])
                except discord.HTTPException as e:
                    logging.warning(f'Error creating emoji "{name}". {e.text}')
                else:
                    message.content = message.content.replace(f'${name}', str(emote))
                    print('replaced w db')
                    emotes_used.append(name)
                    delete_queue.append(emote)

        if emotes_used:
            # Send the emotified message and remove the
            try:
                await self.send_as_user(message.author, message.content, message.channel)
                # sent = await self.send_as_user(message.author, message.content, message.channel)
            except discord.HTTPException as e:
                logging.warning(f'Failed to send emoted message. {e.text}')
            finally:
                for item in delete_queue:
                    await item.delete()

            # Update emote usage statistics (used by the cacher)
            filter_ = {'_id': {'$in': emotes_used}}
            update = {'$inc': {'uses': 1}}
            await self.stats.update_many(filter_, update, upsert=True)

    async def send_as_user(self, member: discord.Member, message: str, channel: discord.TextChannel):
        """Post a webhook that looks like a message sent by the user."""

        # Webhook usernames require at least 2 characters
        username = member.display_name.ljust(2, INVISIBLE_CHAR)
        utils = self.bot.get_cog('Utils')
        if not utils:
            return

        webhook = await utils.get_webhook_for_channel(channel)
        if webhook:
            message = await webhook.send(
                username=username,
                content=message,
                avatar_url=member.avatar_url,
                wait=True)

def setup(bot):
    bot.add_cog(Emoter(bot))