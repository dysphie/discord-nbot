import asyncio
import logging
import re
from datetime import datetime, timedelta
from pprint import pprint
from time import time
from typing import TypedDict, Union
import discord
from discord.ext import commands
from pymongo.errors import DuplicateKeyError
from discord.utils import escape_markdown as nomd

EMOTE_PATTERN = re.compile(r'\$([^\s$]+)')
INVISIBLE_CHAR = '\u17B5'


# FIXME: Already defined in emote_collection_updater.py
class DatabaseEmote(TypedDict):
    _id: str
    url: str
    src: Union[int, str]


class Emoter(commands.Cog):

    def __init__(self, bot):
        self.session = bot.session
        self.emotes = bot.db['newporter.emotes']
        self.blacklist = bot.db['newporter.blacklist']
        self.stats = bot.db['newporter.stats']
        self.emote_guild = None
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.emote_guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])

    @commands.group()
    async def emoter(self, ctx):
        pass

    @emoter.command()
    async def add(self, ctx, name: str, url: str):
        try:
            emote = await self.upload_emote_from_url(name, url)
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
        emote_cache_updater = self.bot.get_cog('EmoteCacheUpdater')
        if emote_cache_updater:
            inserted = await emote_cache_updater.update()
            await ctx.success(f'Cached {inserted} emotes')

    @update.command()
    async def db(self, ctx):
        await ctx.info('Forcing emote database update ...')

    @commands.is_owner()
    @emoter.command()
    async def disable(self, ctx, emote_name: str):
        try:
            await self.blacklist.insert_one({'_id': emote_name}, upsert=True)
        except Exception as e:
            await ctx.error(e)
        else:
            await ctx.success(f'Emote `{emote_name}` **disabled**')

    @commands.is_owner()
    @emoter.command()
    async def enable(self, ctx, emote_name: str):
        try:
            await self.blacklist.delete_one({'_id': emote_name})
        except Exception as e:
            await ctx.error(e)
        else:
            await ctx.success(f'Emote `{emote_name}` **enabled**')

    @emoter.command()
    async def remove(self, ctx, name):
        doc = await self.emotes.find_one_and_delete({'_id': name, 'src': ctx.author.id})
        await ctx.success(f'Deleted emote `${name}`' if doc else 'Emote not found or you are not the owner')

    @emoter.command()
    async def info(self, ctx):

        # Emote collection info
        emote_col_update_info = 'Emote collection updater not loaded'
        emote_col_updater = self.bot.get_cog('EmoteCollectionUpdater')
        if emote_col_updater:
            last_updated, success = await emote_col_updater.get_last_update_info()
            if last_updated:
                time_difference = datetime.now() - last_updated
                hours_passed = round(time_difference / timedelta(hours=1))
                emote_col_update_info = f'{hours_passed} hours ago {"" if success else " (Failed)"}'
            else:
                emote_col_update_info = 'Never'

        # Emote cache info
        emote_cache_update_info = 'Emote cache updater not loaded'
        emote_cache_updater = self.bot.get_cog('EmoteCacheUpdater')
        if emote_cache_updater:
            last_updated = await emote_cache_updater.get_last_update_time()
            if last_updated:
                hours_passed = round((datetime.now() - last_updated) / timedelta(hours=1))
                emote_cache_update_info = f'{hours_passed} hours ago'
            else:
                emote_cache_update_info = 'Never'

        emote_db_count = await self.emotes.count_documents({})

        cached_preview = "None"
        cached_emotes = self.emote_guild.emojis
        if cached_emotes:
            cached_preview = " ".join([f'`{nomd(e.name)}`' for e in cached_emotes])

        cached_current = len(cached_emotes)
        cached_max = self.emote_guild.emoji_limit - 10  # TODO: Softcode
        embed = discord.Embed(description='_ _', color=0x99EE44)
        embed.add_field(inline=False, name='Emotes in cache', value=cached_preview)
        embed.add_field(inline=False, name='Cache capacity', value=f'{cached_current}/{cached_max}')
        embed.add_field(inline=False, name='Emotes in database', value=emote_db_count)
        embed.add_field(inline=False, name='Last updated emote database', value=emote_col_update_info)
        embed.add_field(inline=False, name='Last updated emote cache', value=emote_cache_update_info)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        self.emote_guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])

    async def upload_emote_from_url(self, name, url, replacements):
        async with self.bot.session.get(url) as response:
            image_bytes = await response.read()
            emote = await self.emote_guild.create_custom_emoji(name=name, image=image_bytes)
            replacements[name] = emote

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message):

        t = time()
        if message.author.bot:
            return

        prefixed_words = list(set(EMOTE_PATTERN.findall(message.content)))
        if not prefixed_words:
            return

        prefixed_words.sort(key=len, reverse=True)  # Avoid replacing nested substrings
        new_content = message.content
        print("Variable setup --- %.8f seconds ---" % (time() - t))

        # if self.emote_guild:
        #     for i, word in enumerate(prefixed_words):
        #         emote = discord.utils.find(lambda m: m.name == word, self.emote_guild.emojis)
        #         if emote:
        #             new_content = new_content.replace(f'${word}', str(emote))
        #             del prefixed_words[i]  # TODO: ..is this safe? (´・ω・`)

        # Find remaining emotes in database

        replacements = {}
        if prefixed_words:
            t = time()
            upload_emotes = []
            async for emote in self.emotes.find({'_id': {'$in': prefixed_words}}):
                upload = asyncio.create_task(
                    self.upload_emote_from_url(emote['_id'], emote['url'], replacements))
                upload_emotes.append(upload)

            await asyncio.gather(*upload_emotes)
            print("Database and upload --- %.8f seconds ---" % (time() - t))

            t = time()
            for word in prefixed_words:
                emote = replacements.get(word)
                if emote:
                    new_content = new_content.replace(f'${word}', str(emote))

            print("Word replacement --- %.8f seconds ---" % (time() - t))

        t = time()
        await self.send_as_user(message.author, new_content, message.channel, wait=True)
        print("Sending message --- %.8f seconds ---" % (time() - t))
        # Cleanup
        asyncio.create_task(message.delete())
        for emote in replacements.values():
            asyncio.create_task(emote.delete())

        # update ++usage many for emote $in prefixed

    async def send_as_user(self, author, content, channel, wait=False):

        webhooks = await channel.webhooks()
        webhook = discord.utils.find(lambda m: m.user.id == self.bot.user.id, webhooks)
        if not webhook:
            webhook = await channel.create_webhook(name='NBot')

        await webhook.send(
            username=author.display_name.ljust(2, INVISIBLE_CHAR),  # Username must be 2 digits long
            content=content,
            avatar_url=author.avatar_url,
            wait=wait
        )


def setup(bot):
    bot.add_cog(Emoter(bot))
