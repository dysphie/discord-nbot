import asyncio
import logging
import re
from abc import abstractmethod
from collections import Coroutine
from datetime import datetime
from io import BytesIO
from typing import TypedDict, Union, List, Tuple, Optional
import discord
from PIL import Image
from aiohttp import ClientSession
from discord import slash_command, ApplicationContext, Member, Webhook, Message, Thread, HTTPException, Forbidden, \
    WebhookMessage, File
from discord.ext import commands, tasks
from discord.types.webhook import PartialWebhook
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import InsertOne, UpdateOne
from pymongo.errors import DuplicateKeyError, BulkWriteError
from discord.utils import escape_markdown as nomd, MISSING

EMOTE_PATTERN = re.compile(r'\$([a-zA-Z0-9]+)')
PARTIAL_CACHED_EMOTE = re.compile(r'(.*)~\d+$')
INVISIBLE_CHAR = '\u17B5'
EMOTE_SIZE_LIMIT = 262144


class CacheEmote:

    def __init__(self, name):
        self.name = name
        self.chunks = []

    async def delete(self):
        delete_tasks = [asyncio.create_task(chunk.delete()) for chunk in self.chunks]
        await asyncio.gather(*delete_tasks)

    def to_string(self):  # TODO: figure out why overriding __str__ doesn't work
        return ''.join(str(e) for e in self.chunks)


class DatabaseEmote(TypedDict):
    _id: str
    url: str
    src: Union[int, str]


class ApiFetcher:

    def __init__(self, collection: AsyncIOMotorCollection, session: ClientSession):
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
            print(f'[...] Inserted {num_inserted}')


class BttvFetcher(ApiFetcher):
    urls = {
        'trending': 'https://api.betterttv.net/3/emotes/shared/trending',
        'shared': 'https://api.betterttv.net/3/emotes/shared/top'
    }
    params = {'offset': 0, 'limit': 100}

    async def fetch(self) -> int:

        print(f'[BTTV] Beggining fetch')

        for section, api_url in self.urls.items():
            for i in range(0, 300):
                bulk = []
                self.params['offset'] = i * 100
                async with self.session.get(api_url, params=self.params) as r:

                    data = await r.json()
                    for e in data:

                        id_ = e["emote"]["id"]
                        name = e['emote']['code']
                        animated = e['emote']['imageType'] == 'gif'
                        url = f'https://cdn.betterttv.net/emote/{id_}/2x'

                        if animated:
                            # Check if the standard emote is too big for discord
                            async with self.session.get(url) as r2:
                                if len(await r2.read()) > EMOTE_SIZE_LIMIT:
                                    # If it is, try using a smaller version
                                    url = f'https://cdn.betterttv.net/emote/{id_}/1x'
                                    async with self.session.get(url) as r3:
                                        if len(await r3.read()) > EMOTE_SIZE_LIMIT:
                                            # If it's still too big, use the static version
                                            url = f'https://cache.ffzap.com/https://cdn.betterttv.net/emote/{id_}/2x'

                        bulk.append(InsertOne({'_id': name, 'src': 'bttv', 'url': url, 'animated': animated}))

                    if bulk:
                        try:
                            await self.collection.bulk_write(bulk, ordered=False)
                        except BulkWriteError as bwe:
                            num_inserted = bwe.details['nInserted']
                        else:
                            # HACKHACK: result.inserted_ids is failing, assume the max got inserted
                            num_inserted = 100
                            # num_inserted = len(result.inserted_ids)
                        finally:
                            print(f'[BTTV] Inserted {num_inserted}')

        new_total = await self.collection.count_documents({'src': 'bttv'})
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

        print(f'[FFZ] Beggining fetch')

        while self.params['page'] <= 200:
            async with self.session.get(self.url, params=self.params) as r:
                data = await r.json()
                bulk = []
                for e in data['emoticons']:
                    name = e['name']
                    url = f"https:{e['urls'].get('2') or e['urls'].get('1')}"
                    bulk.append(UpdateOne(
                        {'_id': name, 'src': 'bttv', 'animated': False},
                        {'$set': {'src': 'ffz', 'url': url}},
                        upsert=True
                    ))

                if not bulk:
                    continue

                # TODO: Now that we update rather than insert, num_inserted returns 0
                num_inserted = 0
                try:
                    result = await self.collection.bulk_write(bulk, ordered=False)
                except BulkWriteError as bwe:
                    num_inserted = bwe.details['nInserted']
                else:
                    num_inserted = len(result.inserted_ids)
                finally:
                    # FIXME: result.inserted_ids not accurate?
                    print(f'[FFZ] Inserted {num_inserted}')

            self.params['page'] += 1

        new_total = await self.collection.count_documents({'src': 'ffz'})
        return new_total


class EmoteCollectionUpdater(commands.Cog):

    def __init__(self, emotes, logs, session):
        self.session = session
        self.emotes = emotes
        self.logs = logs

        self.bttv = BttvFetcher(collection=self.emotes, session=self.session)
        self.ffz = FfzFetcher(collection=self.emotes, session=self.session)

    async def get_last_update_info(self) -> Tuple[Optional[datetime], Optional[bool]]:
        result = await self.logs.find_one({'_id': 'lastEmoteCollectionUpdate'})
        if result:
            return result['date'], result['success']
        return None, None

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
            await self.emotes.delete_many({'src': {'$in': ['bttv', 'ffz']}})
            await self.bttv.fetch()
            await self.ffz.fetch()
        except Exception as e:
            logging.error(f'Something went wrong updating the emote collection: {e}')
        else:
            success = True

        await self.logs.update_one(
            {'_id': 'lastEmoteCollectionUpdate'},
            {'$set': {'date': datetime.now(), 'success': success}},
            upsert=True)


class Cache:
    BUFFER_SIZE = 8

    def __init__(self, guild, session):
        self.guild = guild
        self.session = session

        # Ensure a BUFFER_SIZE gap between new insertions and deletions
        asyncio.create_task(self.ensure_space())

    def get_emote(self, name: str) -> CacheEmote:
        chunks = [e for e in self.guild.emojis if re.match(fr'{re.escape(name)}(_\d+)?$', e.name)]
        if chunks:
            emote = CacheEmote(name)
            emote.chunks = chunks
            return emote

    async def evict_emotes(self, count: int):
        tail = sorted(self.guild.emojis, key=lambda e: e.created_at, reverse=False)[:count]
        delete_tasks = [asyncio.create_task(self.delete_emote(e.name)) for e in tail]
        await asyncio.gather(*delete_tasks)

    async def delete_emote(self, name: str):
        emote = self.get_emote(name)
        if emote:
            await emote.delete()

    async def purge(self):
        for emote in self.guild.emojis:
            await emote.delete()

    @staticmethod
    def preprocess_emote(img_bytes: bytes) -> List[bytes]:

        MIN_HEIGHT = 48
        MIN_WIDTH = 48
        MAX_WIDTH = MIN_WIDTH * 3

        with Image.open(BytesIO(img_bytes)) as img:

            if img.is_animated:
                return [img_bytes]

            # Resize and pad with transparency
            img.thumbnail((MAX_WIDTH, MIN_HEIGHT))
            num_slices = round(img.size[0] / MIN_WIDTH)

            # Skip padding for single-cell emotes, not worth it
            if num_slices == 1:
                with BytesIO() as io:
                    img.save(io, 'PNG')
                    io.seek(0)
                    return [io.read()]
            else:
                cells = []
                bg_width = MIN_WIDTH * num_slices
                bg = Image.new('RGBA', (bg_width, MIN_HEIGHT), (255, 255, 255, 0))
                bg.paste(img)

                # Chop it up
                for i in range(num_slices):
                    left = i * MIN_WIDTH
                    right = left + MIN_WIDTH
                    bbox = (left, 0, right, MIN_HEIGHT)
                    cell = img.crop(bbox)
                    with BytesIO() as io:
                        cell.save(io, 'PNG')
                        io.seek(0)
                        cells.append(io.read())

                return cells

    async def upload_emote(self, name: str, url: str) -> Optional[CacheEmote]:

        async with self.session.get(url) as response:
            if response.status != 200:
                return
            img = await response.read()

        sliced_imgs = self.preprocess_emote(img)

        upload_tasks = [
            asyncio.create_task(self.guild.create_custom_emoji(
                name=f"{name}_{i}", image=slice_)
            )
            for i, slice_ in enumerate(sliced_imgs)
        ]

        big_emote = CacheEmote(name)

        try:
            uploaded = await asyncio.gather(*upload_tasks)
        except discord.HTTPException:  # If one chunk fails to upload, cancel and undo the rest
            for task in upload_tasks:
                task.cancel()
            for already_uploaded in big_emote.chunks:  # TODO: Single task for all of them?
                asyncio.create_task(already_uploaded.delete())
        else:
            big_emote.chunks = uploaded
            asyncio.create_task(self.ensure_space())
            return big_emote

    async def ensure_space(self):

        static, animated = [], []
        for emote in self.guild.emojis:
            (static, animated)[emote.animated].append(emote)

        to_delete = set()

        for emote_list in [static, animated]:
            excess_count = len(emote_list) - (self.max - self.BUFFER_SIZE)
            if excess_count < 1:
                continue

            excess_emotes = sorted(emote_list, key=lambda e: e.created_at)[:excess_count]
            for excess_emote in excess_emotes:
                if excess_emote not in to_delete:
                    big_emote = self.get_emote(excess_emote.name)
                    if big_emote:
                        for chunk in big_emote.chunks:
                            to_delete.add(chunk)

        delete_tasks = [asyncio.create_task(d.delete()) for d in to_delete]
        await asyncio.gather(*delete_tasks)

    @property
    def used(self):
        return len(self.guild.emojis)

    @property
    def max(self):
        return self.guild.emoji_limit

    @property
    def free(self):
        return self.max - self.used


class Emoter(commands.Cog):

    def __init__(self, bot):
        self.session = bot.session
        self.emotes = bot.db['emoter.emotes']
        self.blacklist = bot.db['emoter.blacklist']
        self.stats = bot.db['emoter.stats']
        self.logs = bot.db['emoter.logs']
        self.cache: Optional[Cache] = None
        self.db_updater = EmoteCollectionUpdater(self.emotes, self.logs, self.session)
        self.bot = bot

    @tasks.loop(hours=1.0)
    async def updater(self):
        await self.db_updater.check_for_updates()

    @commands.Cog.listener()
    async def on_ready(self):
        emote_guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])
        if emote_guild:
            self.cache = Cache(emote_guild, self.session)

        self.updater.start()

    @commands.group()
    async def emoter(self, ctx):
        pass

    @emoter.group()
    async def db(self, ctx):
        pass

    @emoter.group()
    async def cache(self, ctx):
        pass

    @slash_command(name="emote", description='Post a random emote from the database')
    async def emote(self, ctx: ApplicationContext):
        print('/emote')
        pipeline = [{'$sample': {'size': 1}}]
        async for doc in self.emotes.aggregate(pipeline):
            emote = await self.cache.upload_emote(doc['_id'], doc['url'])
            await ctx.respond(emote.to_string())

    @commands.max_concurrency(1)
    @commands.is_owner()
    @cache.command()
    async def purge(self, ctx):
        try:
            await self.cache.purge()
        except Exception as e:
            await ctx.error(e)
        else:
            await ctx.success('Purged cache')

    @commands.is_owner()
    @cache.command()
    async def info(self, ctx):
        cached_emotes = ''.join(f'`{e.name}` ' for e in self.cache.guild.emojis)
        embed = discord.Embed(color=0x8cc63e)
        embed.add_field(inline=True, name='Capacity', value=f'{self.cache.used}/{self.cache.max}')
        embed.add_field(inline=True, name='Buffer size', value=f'{self.cache.BUFFER_SIZE}')
        embed.add_field(inline=False, name='Cached', value=cached_emotes or 'None')
        await ctx.send(embed=embed)

    @emoter.command()
    async def add(self, ctx, name: str, url: str):
        try:
            await self.emotes.insert_one(DatabaseEmote(_id=name, url=url, src=ctx.author.id))
        except DuplicateKeyError:
            await ctx.info(f'Emote already exists')
        else:
            await ctx.success(f"Added emote `${name}`")

    @commands.max_concurrency(1)
    @commands.is_owner()
    @db.command()
    async def update(self, ctx):
        try:
            await ctx.info('Forcing emote database update ...')
            await self.db_updater.update()
        except Exception as e:
            await ctx.error(e)
        else:
            await ctx.success('Emote database updated')

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
    async def edit(self, ctx, emote_name: str, url: str):
        try:
            await self.blacklist.update_one({'_id': emote_name}, {'$set': {'url': url}})
        except Exception as e:
            await ctx.error(e)
        else:  # TODO: Verbose if doesn't exist
            await ctx.success(f'Emote `{nomd(emote_name)}` edited')

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

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: Message):

        if message.author.bot:
            return

        content = message.content

        single_emote = True
        prefixed = []
        words = content.split()

        for word in words:
            if word.startswith('$'):
                prefixed.append(word[1:])
            else:
                single_emote = False

        num_prefixed = len(prefixed)
        if num_prefixed == 0:
            return

        # if the message is nothing but an emoji, we can cut some corners
        # TODO: Resize if taller than 48px, handle extension properly (.gif seems to work for all)
        if num_prefixed == 1 and single_emote:

            # first do the cache lookup as normal
            big_emote = self.cache.get_emote(prefixed[0])
            if big_emote:
                await self.send_as_user(message, big_emote.to_string(), None)
                await message.delete()
            # else we dont have to upload anything, we can just send as an attachment
            else:
                doc = await self.emotes.find_one({'_id': prefixed[0]})
                if doc:
                    bruh = await self.session.get(doc['url'])
                    data = await bruh.read()
                    await self.send_as_user(message, None, discord.File(BytesIO(data), f'{prefixed[0]}.gif'))
                    await message.delete()
                # if all fails, do an extra lookup in 7tv
                else:
                    img = await self.query_7tv_emote(prefixed[0])
                    if img:
                        print('sending from 7tv!')
                        await self.send_as_user(message, None, discord.File(BytesIO(img), f'{prefixed[0]}.gif'))
                        await message.delete()
            return

        replacements = {}
        search_in_db = []

        # Search for words in emote cache
        for word in prefixed:
            big_emote = self.cache.get_emote(word)
            if big_emote:
                replacements[word] = big_emote.to_string()
            else:
                search_in_db.append(word)

        # Search remaining words in database
        if search_in_db:
            upload_tasks = []
            async for doc in self.emotes.find({'_id': {'$in': search_in_db}}):
                upload_task = asyncio.create_task(self.cache.upload_emote(doc['_id'], doc['url']))
                upload_tasks.append(upload_task)

            big_emotes = await asyncio.gather(*upload_tasks)
            for big_emote in big_emotes:
                replacements[big_emote.name] = big_emote.to_string()



        # If there are still words left, search for them in the database
        if not replacements:
            return

        # TODO: Sort keys by length so as to prevent substring replacement infighting

        for word, replacement in replacements.items():
            content = content.replace(f'${word}', replacement)

        try:
            await self.send_as_user(message, content, None)
        except Exception as e:
            logging.warning(e)
        else:
            await message.delete()

    async def send_as_user(self, msg: Message, content: Optional[str], file: Optional[File]) -> Optional[WebhookMessage]:

        is_thread = isinstance(msg.channel, Thread)
        if is_thread:
            channel = msg.channel.parent
        else:
            channel = msg.channel

        webhooks = await channel.webhooks()
        webhook: Webhook = discord.utils.find(lambda m: m.user.id == self.bot.user.id, webhooks)
        if not webhook:
            try:
                webhook = await channel.create_webhook(name='NBot')
            except (HTTPException, Forbidden):
                return None

        args = {
            'username': msg.author.display_name.ljust(2, INVISIBLE_CHAR),
            'avatar_url': msg.author.display_avatar,
            'wait': True
        }

        if content:
            args['content'] = content
        if file:
            args['file'] = file

        if is_thread:
            args['thread'] = msg.channel

        await webhook.send(**args)

    async def query_7tv_emote(self, keyword) -> Optional[bytes]:

                async with self.session.post('https://api.7tv.app/v2/gql', json={
                    'query': 'query($query: String!,$page: Int,$pageSize: Int,$globalState: String,$sortBy: String,$sortOrder: Int,$channel: String,$submitted_by: String,$filter: EmoteFilter) {search_emotes(query: $query,limit: $pageSize,page: $page,pageSize: $pageSize,globalState: $globalState,sortBy: $sortBy,sortOrder: $sortOrder,channel: $channel,submitted_by: $submitted_by,filter: $filter) {id,visibility,owner {id,display_name,role {id,name,color},banned}name,tags}}',
                    'variables': {
                        "query": keyword,
                        "page": 1,
                        "pageSize": 1,
                        "limit": 1,
                        "globalState": None,
                        "sortBy": "popularity",
                        "sortOrder": 0,
                        "channel": None,
                        "submitted_by": None
                    },
                }) as gql_response:
                    # return the response
                    gql_json = await gql_response.json()

                    emote_name = gql_json['data']['search_emotes'][0]['name']
                    if emote_name.lower() != keyword.lower():
                        return

                    # get the emote id
                    emote_id = gql_json['data']['search_emotes'][0]['id']
                    print(emote_id)

                    # create a request to get the emote
                    emote_url = f'https://cdn.7tv.app/emote/{emote_id}/2x'
                    async with self.session.get(emote_url) as cdn_response:
                        print(f'Got emote from {emote_url}')
                        img = await cdn_response.read()
                        pil_img = Image.open(BytesIO(img))
                        pil_img.info.pop('background', None)
                        with BytesIO() as io:
                            pil_img.save(io, 'gif', save_all=True)
                            io.seek(0)
                            return io.read()

def setup(bot):
    bot.add_cog(Emoter(bot))
