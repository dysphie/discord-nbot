import logging
import re
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict

import discord
import pymongo
from discord.ext import commands, tasks
from pymongo.errors import BulkWriteError, DuplicateKeyError
from abc import ABCMeta

EMOTE_PATTERN = re.compile(r'\$([^\s$]+)')
INVISIBLE_CHAR = '\u17B5'


@dataclass
class DatabaseEmote:
    name: str
    url: str
    owner: int


class DatabaseEmoteBatch:

    def __init__(self, emotes: List[DatabaseEmote], source: str):
        self.emotes = emotes
        self.source = source

    def to_list(self) -> List[Dict]:
        return_list = []
        for e in self.emotes:
            return_list.append({'name': e.name, 'url': e.url, 'owner': e.owner})
        return return_list

    @property
    def length(self):
        return len(self.emotes)


class EmoteCollectionUpdater:

    def __init__(self, logs, emotes, session):
        self.session = session
        self.logs = logs
        self.emotes = emotes

        bttv = BttvApiFetcher(self)
        ffz = FfzApiFetcher(self)
        self.workers = [bttv, ffz]

    async def get_last_update_time(self):
        result = await self.logs.find_one({'_id': 'lastEmoteCollectionUpdate'})
        return result['date'] if result else datetime.min

    async def check_for_updates(self):
        last_update_time = await self.get_last_update_time()
        if (datetime.now() - last_update_time).days < 7:
            print('EmoteCollectionUpdater: No update needed')
            return

        await self.update()

    async def update(self):
        await self.emotes.create_index([("name", pymongo.DESCENDING)], unique=True)

        for worker in self.workers:
            await worker.pull_emotes()
        # TODO: Confirm it was successful

        await self.logs.update_one({'_id': 'lastEmoteCollectionUpdate'}, {'$set': {'date': datetime.now()}},
                                   upsert=True)

    async def insert_emotes(self, emotes: DatabaseEmoteBatch):

        print(f'Inserting {emotes.length} emotes from {emotes.source}')

        num_inserted = 0
        try:
            result = await self.emotes.insert_many(emotes.to_list(), ordered=False)
        except BulkWriteError as bwe:
            num_inserted = bwe.details['nInserted']
        else:
            num_inserted = len(result.inserted_ids)
        finally:
            print(f'Inserted {num_inserted} emotes')

    async def purge_by_source(self, source_id: str):
        try:
            deleted = await self.emotes.delete_many({'source': 'bttv'})
        except Exception as e:
            print(e)
        else:
            print(f'[{source_id}] Deleted {deleted.deleted_count} existing emotes')


class EmoteApiFetcher(metaclass=ABCMeta):

    @abstractmethod
    def __init__(self, emote_mgr: EmoteCollectionUpdater):
        self.mgr = emote_mgr

    @abstractmethod
    async def pull_emotes(self):
        pass


class BttvApiFetcher(EmoteApiFetcher):

    def __init__(self, emote_mgr):
        super(BttvApiFetcher, self).__init__(emote_mgr)

    id = "bttv"
    urls = {
        'trending': 'https://api.betterttv.net/3/emotes/shared/trending',
        'shared': 'https://api.betterttv.net/3/emotes/shared/top'
    }
    params = {'offset': 0, 'limit': 100}

    async def pull_emotes(self):

        print(f'[{self.id}] Backing up emotes')

        for section, url in self.urls.items():
            for i in range(0, 200):

                emotes: List[DatabaseEmote] = []

                self.params['offset'] = i * 100
                async with self.mgr.session.get(url, params=self.params) as r:
                    if r.status != 200:
                        raise Exception(f'[{self.id}] API responded with status {r.status}')

                    data = await r.json()

                    for e in data:
                        name = e['emote']['code']
                        url = f'https://cdn.betterttv.net/emote/{e["emote"]["id"]}/2x'

                        emote = DatabaseEmote(name=name, url=url, owner=0)
                        emotes.append(emote)

                    if not emotes:
                        break

                    await self.mgr.insert_emotes(DatabaseEmoteBatch(emotes, self.id))

        print(f'[{self.id}] Finished import')


class FfzApiFetcher(EmoteApiFetcher):
    id = 'ffz'
    url = 'https://api.frankerfacez.com/v1/emoticons'
    params = {
        'high_dpi': 'off',
        'sort': 'count-desc',
        'per_page': 200,
        'page': 1
    }

    def __init__(self, emote_mgr: EmoteCollectionUpdater):
        super().__init__(emote_mgr)

    async def pull_emotes(self):

        print(f'[{self.id}] Backing up emotes')
        await self.backup_from_page(1)
        print(f'[{self.id}] Finished import')

    async def backup_from_page(self, page_num: int):

        self.params['page'] = page_num  # Update request headers

        async with self.mgr.session.get(self.url, params=self.params) as r:
            if r.status != 200:
                raise Exception(f'[{self.id}] API responded with status {r.status}')

            data = await r.json()

            emotes: List[DatabaseEmote] = list()

            for e in data['emoticons']:
                name = e['name']
                url = e['urls'].get('2') or e['urls'].get('1')
                emote = DatabaseEmote(name=name, url=url, owner=0)
                emotes.append(emote)

            await self.mgr.insert_emotes(DatabaseEmoteBatch(emotes, self.id))

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

    async def get_last_update_time(self):
        result = await self.logs.find_one({'_id': 'lastCacheUpdate'})
        return result['date'] if result else datetime.min

    async def check_for_updates(self):
        last_update_time = await self.get_last_update_time()
        if (datetime.now() - last_update_time).days < 2:
            print('EmoteCacheUpdater: No update needed')
            return
        await self.update()

    async def get_most_used_emotes(self, limit: int) -> dict:

        query = [
            {'$match': {'uses': {'$gt': 0}}},  # Get emotes that have been used at least once
            {'$sort': {'uses': -1}},  # Sort by most uses
            {'$limit': limit},
            {
                # Get array of objects whose `name` matches an `_id` returned by the stats db
                '$lookup': {
                    'from': 'emoter.emotes',
                    'let': {'name': '$_id'},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$name', '$$name']}}},
                        {'$limit': 1},  # For sanity's sake, there should never be multiple results
                        {'$project': {'url': 1}}
                    ],
                    'as': 'emote_data'
                }
            },
            # Array can only have one object, so extract url from the object and make it a simple top field
            {'$project': {'url': {'$arrayElemAt': ['emote_data.url', 0]}}}
        ]

        results = {}
        async for doc in self.stats.aggregate(query):
            results[doc['_id']] = doc['url']

        return results

    async def update(self):

        most_used: dict = await self.get_most_used_emotes(40)
        if not most_used:
            logging.warning('Database returned no data for most used emotes')
            return

        for emote in self.guild.emojis:
            await emote.delete()

        num_uploaded = 0
        for name, url in most_used.items():
            async with self.session.get(url) as response:
                if response.status == 200:
                    image = await response.read()
                    try:
                        await self.guild.create_custom_emoji(name=name, image=image)
                    except discord.HTTPException:
                        pass
                    finally:
                        num_uploaded += 1

        num_failed = len(most_used) - num_uploaded
        print(f'EmoteCacheUpdater: Caching complete. Uploaded: {num_uploaded}. Failed: {num_failed}')
        await self.logs.update_one({'_id': 'lastCacheUpdate'}, {'$set': {'date': datetime.now()}}, upsert=True)


class EmoteDatabaseUpdateResults:

    def __init__(self, successful: bool, error: str, num_inserted: int):
        self.successful = successful
        self.error = error
        self.num_inserted: num_inserted


class Emoter(commands.Cog):

    def __init__(self, bot):
        self.logs = bot.db['emoter.logs']
        self.emotes = bot.db['emoter.emotes']
        self.stats = bot.db['emoter.stats']
        self.clientprefs = bot.db['emoter.clientprefs']
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

    @commands.group()
    async def emoter(self, ctx):
        pass

    @emoter.command()
    async def add(self, ctx, name: str, url: str):
        try:
            emote = await self.upload_emote_from_url(self.emote_guild, name, url)
        except discord.HTTPException as e:
            await ctx.send(e)
        else:
            try:
                await self.emotes.insert_one({
                    'owner': ctx.author.id,
                    '_id': name,
                    'url': str(emote.url),
                    'uses': 1
                })
            except DuplicateKeyError:
                await ctx.send(f'Emote with that name already exists')
            else:
                await ctx.send(f'Added emote `${name}`')
            finally:
                await emote.delete()

    @commands.max_concurrency(1)
    @commands.is_owner()
    @emoter.group()
    async def update(self, ctx):
        pass

    @update.command()
    async def cache(self, ctx):
        await ctx.info('Forcing emote cache update ...')

    @update.command()
    async def db(self, ctx):
        await ctx.info('Forcing emote database update ...')

    @commands.is_owner()
    @emoter.command()
    async def disable(self, ctx, emote_name: str):
        try:
            result = await self.emotes.update_one(
                {'name': emote_name},
                {'$set': {'enabled': False}}
            )
        except Exception as e:
            await ctx.error(f'Operation failed: {e}')
        else:
            emote_name = discord.utils.escape_markdown(emote_name)

            if result.modifiedCount:
                await ctx.success(f'Emote `{emote_name}` **disabled**')
            else:
                await ctx.warning(f'Emote `{emote_name}` was not found')

    @commands.is_owner()
    @emoter.command()
    async def enable(self, ctx, emote_name: str):
        try:
            result = await self.emotes.update_one(
                {'name': emote_name},
                {'$set': {'enabled': True}}
            )
        except Exception as e:
            await ctx.error(f'Operation failed: {e}')
        else:
            emote_name = discord.utils.escape_markdown(emote_name)

            if result.modifiedCount:
                await ctx.success(f'Emote `{emote_name}` **disabled**')
            else:
                await ctx.warning(f'Emote `{emote_name}` was not found')

    @emoter.command()
    async def prefix(self, ctx, prefix: str):

        try:
            await self.clientprefs.update_one(
                {'_id': ctx.author.id},
                {'$set': {'prefix': prefix}},
                upsert=True
            )
        except Exception as e:
            await ctx.error(f'Operation failed: {e}')
        else:
            prefix = discord.utils.escape_markdown(prefix)
            await ctx.success(f'Emote prefix set to `{prefix}`')

    @emoter.command()
    async def remove(self, ctx, name):
        doc = await self.emotes.find_one_and_delete({'_id': name, 'owner': ctx.author.id})
        await ctx.send(f'Deleted emote `${name}`' if doc else 'Emote not found or you are not the owner')

    @emoter.command()
    async def info(self, ctx):
        # FIXME: This will probably hit the character limit

        cache_last_updated = await self.cache_updater.get_last_update_time()  # TODO: could be null
        emotes_last_updated = await self.emotes_updater.get_last_update_time()
        emote_db_count = await self.emotes.estimated_document_count()
        cached_emotes = self.emote_guild.emojis
        cached_preview = " ".join([f'{str(e)}' for e in cached_emotes])
        cached_current = len(cached_emotes)
        cached_max = self.emote_guild.emoji_limit - 10  # TODO: Softcode
        embed = discord.Embed(description='_ _', color=0x99EE44)
        embed.add_field(inline=False, name='Emotes in cache', value=cached_preview)
        embed.add_field(inline=False, name='Cache capacity', value=f'{cached_current}/{cached_max}')
        embed.add_field(inline=False, name='Emotes in database', value=emote_db_count)
        embed.add_field(inline=False, name='Last updated emote database', value=emotes_last_updated)
        embed.add_field(inline=False, name='Last updated emote cache', value=cache_last_updated)
        await ctx.send(embed=embed)

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
    @commands.guild_only()
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
                    emote = await self.upload_emote_from_url(self.emote_guild, name, emote['url'])
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
            await webhook.send(username=username, content=message, avatar_url=member.avatar_url, wait=True)


def setup(bot):
    bot.add_cog(Emoter(bot))
