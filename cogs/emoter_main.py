import logging
import math
import re
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO
from typing import TypedDict, Union, List, Tuple, Optional
import discord
from PIL import Image
from aiohttp import ClientSession
from discord import Emoji, Guild
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, BulkWriteError
from discord.utils import escape_markdown as nomd

EMOTE_PATTERN = re.compile(r'\$([^\s$]+)')
PARTIAL_CACHED_EMOTE = re.compile(r'(.*)~\d+$')
INVISIBLE_CHAR = '\u17B5'


class DatabaseEmote(TypedDict):
    _id: str
    url: str
    src: Union[int, str]


class ApiFetcher:

    def __init__(self, uid, collection: AsyncIOMotorCollection, session: ClientSession):
        self.uid = uid
        self.collection = collection
        self.session = session

    @abstractmethod
    async def fetch(self) -> int:
        raise NotImplementedError("API fetcher must implement fetch()")

    async def save_emotes(self, database_emotes: List[DatabaseEmote]):
        num_inserted = 0
        try:
            result = await self.collection.insert_many(database_emotes, ordered=False)
        except BulkWriteError as bwe:
            num_inserted = bwe.details['nInserted']
        else:
            num_inserted = len(result.inserted_ids)
        finally:
            print(f'[{self.uid}] Inserted {num_inserted}')


class BttvFetcher(ApiFetcher):
    urls = {
        'trending': 'https://api.betterttv.net/3/emotes/shared/trending',
        'shared': 'https://api.betterttv.net/3/emotes/shared/top'
    }
    params = {'offset': 0, 'limit': 100}

    async def fetch(self) -> int:

        print(f'[{self.uid}] Beggining fetch')
        await self.collection.delete_many({'src': self.uid})

        for section, url in self.urls.items():
            for i in range(0, 200):
                self.params['offset'] = i * 100
                emotes = []
                async with self.session.get(url, params=self.params) as r:
                    data = await r.json()
                    for e in data:
                        emote = DatabaseEmote(
                            _id=e['emote']['code'],
                            url=f'https://cdn.betterttv.net/emote/{e["emote"]["id"]}/2x',
                            src=self.uid
                        )
                        emotes.append(emote)

                    if not emotes:
                        break

                    await self.save_emotes(emotes)

        new_total = await self.collection.count_documents({'src': self.uid})
        return new_total


class FfzFetcher(ApiFetcher):
    url = 'https://api.frankerfacez.com/v1/emoticons'
    params = {
        'high_dpi': 'off',
        'sort': 'count-desc',
        'per_page': 200,
        'page': 1
    }

    async def fetch(self):

        print(f'[{self.uid}] Beggining fetch')
        await self.collection.delete_many({'src': self.uid})

        while self.params['page'] <= 200:
            async with self.session.get(self.url, params=self.params) as r:
                data = await r.json()
                emotes = []
                for e in data['emoticons']:
                    emote = DatabaseEmote(
                        _id=e['name'], src=self.uid,
                        url=e['urls'].get('2') or e['urls'].get('1')
                    )
                    emotes.append(emote)
                await self.save_emotes(emotes)

            self.params['page'] += 1

        new_total = await self.collection.count_documents({'src': self.uid})
        return new_total


class EmoteCollectionUpdater(commands.Cog):

    def __init__(self, emotes, logs, session):
        self.session = session
        self.emotes = emotes
        self.logs = logs

        bttv = BttvFetcher(uid=1, collection=self.emotes, session=self.session)
        ffz = FfzFetcher(uid=2, collection=self.emotes, session=self.session)
        self.apis = (bttv, ffz)

    async def get_last_update_info(self) -> Tuple[Optional[datetime], Optional[bool]]:

        result = await self.logs.find_one({'_id': 'lastEmoteCollectionUpdate'})
        if result:
            return result['date'], result['success']

    async def check_for_updates(self):
        logging.debug(f'Checking for emote updates..')
        last_update_time, success = await self.get_last_update_info()
        logging.debug(f'Last update: {last_update_time} (Success: {success})')
        if not success or not datetime or (datetime.now() - last_update_time).days > 7:
            await self.update()

    async def update(self):
        logging.debug('Begin emote update..')
        success = False
        try:
            for api in self.apis:
                await api.fetch()
        except Exception as e:
            logging.error(f'Something went wrong updating the emote collection: {e}')
        else:
            success = True

        await self.logs.update_one(
            {'_id': 'lastEmoteCollectionUpdate'},
            {'$set': {'date': datetime.now(), 'success': success}},
            upsert=True)


class Cache:

    def __init__(self, guild, logs, stats, emotes, session):
        self.guild: Guild = guild
        self.session = session
        self.stats = stats
        self.logs = logs
        self.emotes = emotes
        self.replacements = {}
        self.build_replacement_table()

    async def get_last_update_time(self):
        result = await self.logs.find_one({'_id': 'lastCacheUpdate'})
        if result:
            return result['date']

    async def check_for_updates(self):
        last_update_time = await self.get_last_update_time()
        if not last_update_time or (datetime.now() - last_update_time).days > 1:
            await self.update()

    async def update(self) -> int:

        #  TODO: Better sanity checks. $lookup instead of 2 queries
        await self.purge()

        top_used = set()
        cursor = self.stats.find({'uses': {'$gt': 0}})
        cursor.sort('uses', -1).limit(40)
        async for doc in cursor:
            top_used.add(doc['_id'])

        num_uploaded = 0
        async for doc in self.emotes.find({'_id': {'$in': list(top_used)}}):
            name = doc['_id']
            try:
                emotes = await self.upload_emote(name=name, url=doc['url'], complex=True)
            except discord.HTTPException:
                pass
            else:
                self.replacements[name] = ''.join(e.name for e in emotes)
                num_uploaded += len(emotes)
                if num_uploaded >= 40:
                    break

        print(f'EmoteCacheUpdater: Caching complete. Uploaded: {num_uploaded}')
        await self.logs.update_one({'_id': 'lastCacheUpdate'}, {'$set': {'date': datetime.now()}}, upsert=True)
        self.build_replacement_table()
        return num_uploaded

    async def purge(self):
        for e in self.guild.emojis:
            await e.delete()
        self.replacements.clear()

    async def upload_emote(self, name: str, url: str, complex=False) -> Union[Emoji, List[Emoji]]:

        async with self.session.get(url) as r:
            img_bytes = await r.read()

        if not complex:
            emote = await self.guild.create_custom_emoji(name=name, image=img_bytes)
            return emote
        else:
            with Image.open(BytesIO(img_bytes)) as pil_img:
                pil_img.thumbnail((144, 48))
                width, height = pil_img.size
                num_chunks = math.ceil(width / 48)
                if num_chunks == 1:
                    # TODO: This is dumb, dry, revamp
                    emote = await self.guild.create_custom_emoji(name=name, image=img_bytes)
                    return [emote]

                emotes = []
                for i in range(num_chunks):
                    left = 48 * i
                    right = width if i == num_chunks - 1 else 48 + left
                    box = (left, 0, right, height)

                    chunk_img_bytes = BytesIO()
                    chunk_img = pil_img.crop(box)
                    chunk_img.save(chunk_img_bytes, "png")  # TODO: Dont hardcode ext
                    chunk_img_bytes.seek(0)

                    emote = await self.guild.create_custom_emoji(name=name, image=chunk_img_bytes.read())
                    emotes.append(emote)

                return emotes

    def build_replacement_table(self):
        replacements = {}
        partials = defaultdict(list)

        for e in self.guild.emojis:
            partial = PARTIAL_CACHED_EMOTE.search(e.name)
            if partial:
                partials[partial.group(1)].append(e)
            else:
                replacements[e.name] = str(e)

        for namespace, emotes in partials.items():
            emotes.sort(key=lambda x: int(''.join(filter(str.isdigit, x.name))))
            replacements[namespace] = ''.join([str(e) for e in emotes])

        self.replacements = replacements

    @property
    def used(self):
        return len(self.guild.emojis)

    @property
    def max(self):
        return self.guild.emoji_limit


class Emoter(commands.Cog):

    def __init__(self, bot):
        self.session = bot.session
        self.emotes = bot.db['newporter.emotes']
        self.blacklist = bot.db['newporter.blacklist']
        self.stats = bot.db['newporter.stats']
        self.logs = bot.db['newporter.logs']
        self.cache = None
        self.db_updater = EmoteCollectionUpdater(self.emotes, self.logs, self.session)
        self.bot = bot

    @tasks.loop(hours=12.0)
    async def updater(self):
        await self.cache.check_for_updates()
        await self.db_updater.check_for_updates()

    @commands.Cog.listener()
    async def on_ready(self):
        self.updater.start()
        emote_guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])
        self.cache = Cache(emote_guild, self.logs, self.stats, self.emotes, self.session)

    @commands.group()
    async def emoter(self, ctx):
        pass

    @emoter.command()
    async def cachetable(self, ctx):
        await ctx.send(self.cache.replacements)

    @emoter.command()
    async def add(self, ctx, name: str, url: str):
        try:
            emote = self.cache.upload_emote(name, url)
        except discord.HTTPException as e:
            await ctx.error(e)
        else:
            try:
                await self.emotes.insert_one(DatabaseEmote(_id=name, url=str(emote.url), src=ctx.author.id))
            except DuplicateKeyError:
                await ctx.info(f'Emote already exists')
            else:
                await ctx.success(f'Added emote `${name}`')
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
        inserted = await self.cache.update()
        await ctx.success(f'Cached {inserted} emotes')

    @update.command()
    async def db(self, ctx):
        await ctx.info('Forcing emote database update ...')

    @commands.is_owner()
    @emoter.command()
    async def disable(self, ctx, emote_name: str):
        try:
            await self.blacklist.insert_one({'_id': emote_name})
        except DuplicateKeyError:
            await ctx.info(f'Emote `{nomd(emote_name)} already disabled')
        else:
            await ctx.success(f'Emote `{nomd(emote_name)}` disabled')

    @commands.is_owner()
    @emoter.command()
    async def enable(self, ctx, emote_name: str):
        try:
            result = await self.blacklist.delete_one({'_id': emote_name})
        except Exception as e:
            await ctx.error(e)
        else:
            if result.deleted_count:
                await ctx.success(f'Emote `{nomd(emote_name)}` enabled')
            else:
                await ctx.info(f'Emote `{nomd(emote_name)} is already enabled')

    @emoter.command()
    async def remove(self, ctx, name):
        doc = await self.emotes.find_one_and_delete({'_id': name, 'src': ctx.author.id})
        await ctx.success(f'Deleted emote `${name}`' if doc else 'Emote not found or you are not the owner')

    @emoter.command()
    async def info(self, ctx):

        # Emote collection info
        last_updated, success = await self.db_updater.get_last_update_info()
        if last_updated:
            time_difference = datetime.now() - last_updated
            hours_passed = round(time_difference / timedelta(hours=1))
            db_update_info = f'{hours_passed} hours ago {"" if success else " (Failed)"}'
        else:
            db_update_info = 'Never'

        # Emote cache info
        last_updated = await self.cache.get_last_update_time()
        if last_updated:
            hours_passed = round((datetime.now() - last_updated) / timedelta(hours=1))
            cache_update_info = f'{hours_passed} hours ago'
        else:
            cache_update_info = 'Never'

        emote_db_count = await self.emotes.count_documents({})
        cached_emotes = ' '.join([f'`{nomd(e.name)}`' for e in self.cache.guild.emojis]) or 'None'

        embed = discord.Embed(description='_ _', color=0x99EE44)
        embed.add_field(inline=False, name='Emotes in cache', value=cached_emotes)
        embed.add_field(inline=False, name='Cache capacity', value=f'{self.cache.used}/{self.cache.max}')
        embed.add_field(inline=False, name='Emotes in database', value=emote_db_count)
        embed.add_field(inline=False, name='Last updated emote database', value=db_update_info)
        embed.add_field(inline=False, name='Last updated emote cache', value=cache_update_info)
        await ctx.send(embed=embed)

    @staticmethod
    async def process_emote(img_bytes: bytes) -> List[bytes]:
        max_size = (144, 48)
        with Image.open(BytesIO(img_bytes)) as pil_img:

            pil_img.thumbnail(max_size)
            width, height = pil_img.size
            if width <= 48:
                return [img_bytes]
            else:
                print('too wide, split into chunks')

                results = []

                num_chunks = int(width / 48)
                for i in range(num_chunks):
                    left = 48 * i
                    if i == num_chunks - 1:
                        right = width
                    else:
                        right = 48 + left
                    box = (left, 0, right, height)

                    bytesio = BytesIO()
                    chunk = pil_img.crop(box)
                    chunk.save(bytesio, "png")
                    bytesio.seek(0)
                    results.append(bytesio.read())

                return results

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message):

        # TODO: This has grown into a mess..
        #  Weed out data structs, optimize, use tasks instead of queued awaits

        if message.author.bot:
            return

        prefixed = list(set(EMOTE_PATTERN.findall(message.content)))
        if not prefixed:
            return

        prefixed.sort(key=len, reverse=True)
        content = message.content
        to_delete = []

        analytics = []

        for i, p in enumerate(prefixed):
            r = self.cache.replacements.get(p)
            if r:
                content = content.replace(f'${p}', r)
                analytics.append(p)
                del prefixed[i]

        # Find remaining emotes in database
        replacements = {}
        if prefixed:
            async for doc in self.emotes.find({'_id': {'$in': prefixed}}):
                name, url = doc['_id'], doc['url']
                emotes = await self.cache.upload_emote(name, url, complex=True)
                replacements[name] = ''.join([str(e) for e in emotes])
                to_delete.extend(emotes)

            for p in prefixed:
                rs = replacements.get(p)
                if rs:
                    print(f'Replace: ${p} ===> {rs}')
                    content = content.replace(f'${p}', rs)
                    analytics.append(p)

        if to_delete:
            # We made replacements, so delete the original message
            # send the emotified version and delete emotes afterwards
            try:
                await self.send_as_user(message.author, content, message.channel, wait=True)
            except discord.HTTPException as e:
                logging.warning(f'Failed to send emoted message. {e.text}')
            finally:
                for item in to_delete:
                    await item.delete()
                await message.delete()

        await self.stats.update_many({'_id': {'$in': analytics}}, {'$inc': {'uses': 1}}, upsert=True)

    async def send_as_user(self, member, content, channel, wait=False):

        username = member.display_name.ljust(2, INVISIBLE_CHAR)
        webhooks = await channel.webhooks()
        webhook = discord.utils.find(lambda m: m.user.id == self.bot.user.id, webhooks)
        if not webhook:
            webhook = await channel.create_webhook(name='NBot')

        if webhook:
            await webhook.send(
                username=username, content=content,
                avatar_url=member.avatar_url, wait=wait
            )


def setup(bot):
    bot.add_cog(Emoter(bot))
