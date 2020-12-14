import asyncio
import logging
import math
import re
from abc import abstractmethod
from datetime import datetime
from io import BytesIO
from time import time
from typing import TypedDict, Union, List, Tuple, Optional
import discord
from PIL import Image
from aiohttp import ClientSession
from discord import Emoji
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
                        if e['emote']['imageType'] == 'gif':
                            emote = DatabaseEmote(
                                _id=e['emote']['code'],
                                url=f'https://cdn.betterttv.net/emote/{e["emote"]["id"]}/2x',
                                src=self.uid
                            )
                            emotes.append(emote)

                    if emotes:
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
                        url=f"https:{e['urls'].get('2') or e['urls'].get('1')}"
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
    BUFFER_SIZE = 8

    def __init__(self, guild, session):
        self.guild = guild
        self.session = session

        # Ensure a BUFFER_SIZE gap between new insertions and deletions
        asyncio.create_task(self.ensure_space())

    def get(self, name: str) -> List[Emoji]:
        return [e for e in self.guild.emojis if re.match(fr'{name}(_\d+)?$', e.name)]

    async def evict(self, count: int):
        deleted = 0
        for emote in sorted(self.guild.emojis, key=lambda e: e.created_at, reverse=True):
            deleted += await self.delete(emote.name)
            if deleted >= count:
                break

    async def delete(self, name: str) -> int:
        emotes = self.get(name)
        for emote in emotes:
            await emote.delete()
        return len(emotes)

    async def purge(self):
        for emote in self.guild.emojis:
            await emote.delete()

    @staticmethod
    def preprocess_emote(img_bytes: bytes) -> List[bytes]:

        # TODO: Width should be rounded to the closest multiplier of 48
        #  Current implementation creates ghost emote (empty)
        slot_max = 48
        with Image.open(BytesIO(img_bytes)) as img:
            cur_width, cur_height = img.size
            # Don't act on GIFs or properly sized emotes
            if (cur_width <= slot_max and cur_height <= slot_max) or img.is_animated:
                return [img_bytes]

            # Set max height to 48px, scale width accordingly
            new_height = slot_max
            new_width = int(new_height * cur_width / cur_height)

            # Calculate how many emote slots the image would occupy
            num_slots = new_width / slot_max

            # If the image would barely occupy the last slot, scale down by one
            if num_slots > 1 and num_slots % 1 < 0.4:
                final_width = new_width - (new_width % slot_max)
                # And finally scale the height based on the rounded down width
                final_height = int(final_width * new_height / new_width)
                num_slots -= 1
            else:
                final_width = new_width
                final_height = new_height
                
            num_slots = math.ceil(num_slots)

            # Perform actual resize operation
            img.resize((final_width, final_height))

            # If the emote is single-image, we are done, return bytes
            if num_slots == 1:
                with BytesIO() as io:
                    img.save(io, 'PNG')
                    io.seek(0)
                    return [io.read()]

            # Else slice..
            slices = []
            for i in range(num_slots):
                left = i * slot_max
                right = left + slot_max
                bbox = (left, 0, right, final_height)
                slice_ = img.crop(bbox)
                with BytesIO() as io:
                    slice_.save(io, 'PNG')
                    io.seek(0)
                    slices.append(io.read())

            return slices

    async def upload_emote(self, name: str, url: str) -> List[Emoji]:

        # TODO: Don't prefix single-image emotes
        async with self.session.get(url) as response:
            if response.status != 200:
                return []

            img = await response.read()
            sliced_imgs = self.preprocess_emote(img)

            uploaded = []
            for i, slice_ in enumerate(sliced_imgs):
                try:
                    emote = await self.guild.create_custom_emoji(name=f'{name}_{i}', image=slice_)
                except Exception:  # If a slice fails, all slices must fail
                    for u in uploaded:
                        await u.delete()
                    return []
                else:
                    uploaded.append(emote)

            asyncio.create_task(self.ensure_space())
            return uploaded

    async def ensure_space(self):
        num_to_evict = self.BUFFER_SIZE - (self.max - self.used)
        if num_to_evict > 0:
            await self.evict(num_to_evict)

    # def build_lookup_table(self):
    #     replacements = {}
    #     partials = defaultdict(list)
    #
    #     for e in self.guild.emojis:
    #         partial = PARTIAL_CACHED_EMOTE.search(e.name)
    #         if partial:
    #             partials[partial.group(1)].append(e)
    #         else:
    #             replacements[e.name] = str(e)
    #
    #     for namespace, emotes in partials.items():
    #         emotes.sort(key=lambda x: int(''.join(filter(str.isdigit, x.name))))
    #         replacements[namespace] = ''.join([str(e) for e in emotes])
    #
    #     self.lookup_table = replacements

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
        self.emotes = bot.db['newporter.emotes']
        self.blacklist = bot.db['newporter.blacklist']
        self.stats = bot.db['newporter.stats']
        self.logs = bot.db['newporter.logs']
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
    async def on_message(self, message):

        # TODO: This has grown into a mess..
        #  Weed out data structs, optimize, use tasks instead of queued awaits

        if message.author.bot:
            return

        content = message.content
        prefixed = sorted(set(EMOTE_PATTERN.findall(content)), key=len, reverse=True)
        if not prefixed:
            return

        for i, p in enumerate(list(prefixed)):
            emotes = self.cache.get(p)
            if emotes:
                content = content.replace(f'${p}', ''.join(str(e) for e in emotes))
                del prefixed[i]

        if prefixed:
            async for doc in self.emotes.find({'_id': {'$in': prefixed}}):
                name, url = doc['_id'], doc['url']
                emotes = await self.cache.upload_emote(name, url)
                if emotes:
                    content = content.replace(f'${name}', ''.join(str(e) for e in emotes))

        if content != message.content:  # Optimize?
            try:
                await self.send_as_user(message.author, content, message.channel)
            except Exception as e:
                logging.warning(e)
            else:
                await message.delete()

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
