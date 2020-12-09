import logging
import re
from datetime import datetime, timedelta
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
            emote = await self.upload_emote_from_url(self.emote_guild, name, url)
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
        prefixed_words.sort(key=len, reverse=True)

        if not self.emote_guild:
            logging.warning('Emoter: Cache is null.')
        else:
            for i, word in enumerate(prefixed_words):
                # Find emote in local guild
                emote = discord.utils.find(lambda m: m.name == word, self.emote_guild.emojis)
                if not emote:
                    # Give up for now
                    continue

                message.content = message.content.replace(f'${word}', str(emote))
                emotes_used.append(word)
                del prefixed_words[i]

        delete_queue = [message]

        # Find remaining emotes in database
        if prefixed_words:
            async for emote in self.emotes.find({'_id': {'$in': prefixed_words}}):
                name = emote['_id']
                try:
                    emote = await self.upload_emote_from_url(self.emote_guild, name, emote['url'])
                except discord.HTTPException as e:
                    logging.warning(f'Error creating emoji "{name}". {e.text}')
                else:
                    message.content = message.content.replace(f'${name}', str(emote))
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
            # TODO: This should be cache cog, where do we put it..?
            await self.stats.update_many({'_id': {'$in': emotes_used}}, {'$inc': {'uses': 1}}, upsert=True)

    async def send_as_user(self, member: discord.Member, message: str, channel: discord.TextChannel):
        """Post a webhook that looks like a message sent by the user."""

        # Webhook usernames require at least 2 characters
        if len(member.display_name) < 2:
            member.display_name.ljust(2, INVISIBLE_CHAR)

        webhook = None
        webhooks = await channel.webhooks()
        for w in webhooks:
            if w.user.id == self.bot.user.id:
                webhook = w
        if not webhook:
            webhook = await channel.create_webhook(name='NBot')

        await webhook.send(
            username=member.display_name,
            content=message,
            avatar_url=member.avatar_url,
            wait=True
        )


def setup(bot):
    bot.add_cog(Emoter(bot))
