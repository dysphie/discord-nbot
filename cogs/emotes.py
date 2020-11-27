import logging
import re
from time import time

import discord
from discord import HTTPException
from discord.ext import commands
from pymongo.errors import DuplicateKeyError

INVISIBLE_CHAR = '\u17B5'
EMOTE_PATTERN = re.compile(r'\$([^\s$]+)')


class Emotes(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db_emotes = bot.db['new_emotes']  # TODO: Fetch from config
        self.session = bot.session
        self.emotes_guild = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.emotes_guild = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot or not self.emotes_guild:
            return

        emotes_used = []

        #  Find all potential emotes (e.g. $duck)
        prefixed_words = list(set(EMOTE_PATTERN.findall(message.content)))
        if not prefixed_words:
            return

        # Avoid replacing $duck for <:duck:123> before replacing $ducks
        prefixed_words.sort(key=len)

        for i, word in enumerate(prefixed_words):
            # Search 'word' in local guild emotes
            emote = discord.utils.find(lambda m: m.name == word, message.channel.guild.emojis)
            if not emote:
                # Search in cache guild emotes
                emote = discord.utils.find(lambda m: m.name == word, self.emotes_guild.emojis)
                if not emote:
                    # Give up for now
                    continue

            message.content = message.content.replace(f'${word}', str(emote))
            emotes_used.append(word)
            del prefixed_words[i]

        delete_queue = [message]

        if not prefixed_words:
            return

            #  Search remaining emotes in database
        async for emote in self.db_emotes.find({'name': {'$in': prefixed_words}}):
            name = emote['name']
            try:
                emote = await self.upload_discord_emote(name, emote['url'])
            except discord.HTTPException as e:
                logging.warning(f'Error creating emoji "{name}". {e.text}')
            else:
                message.content = message.content.replace(f'${name}', str(emote))
                emotes_used.append(name)
                delete_queue.append(emote)

        try:
            sent = await self.impersonate(message.author, message.content, message.channel)
        except HTTPException as e:
            logging.warning(f'Failed to send emoted message. {e.text}')
        else:
            if sent:
                for item in delete_queue:
                    await item.delete()

        print(f'TODO: Save {emotes_used}')

    async def upload_discord_emote(self, name: str, url: str):
        async with self.session.get(url) as response:
            if response.status != 200:
                raise discord.HTTPException(response.status, "Invalid URL")

            image_bytes = await response.read()
            emote = await self.emotes_guild.create_custom_emoji(name=name, image=image_bytes)
            return emote

    @commands.command()
    async def add(self, ctx, name, url):
        try:
            emote = await self.upload_discord_emote(name, url)
        except discord.HTTPException as e:
            await ctx.send('Discord rejected the emote (too big?)')
        else:
            try:
                await self.db_emotes.insert_one({
                    'owner': ctx.author.id,
                    'name': name,
                    'url': str(emote.url),
                    'source': 'user'
                })
            except DuplicateKeyError:
                await ctx.send(f'Emote with that name already exists')
            else:
                await ctx.send(f'Added emote `${name}`')
            finally:
                await emote.delete()

    @commands.command()
    async def remove(self, ctx, name):
        deleted = await self.db_emotes.find_one_and_delete({'name': name, 'owner': ctx.author.id})
        if deleted:
            await ctx.send(f'Deleted `${name}`')
        else:
            await ctx.send("Couldn't find emote. Either it doesn't exist or you are not the owner")

    async def impersonate(self, member: discord.Member, message: str, channel: discord.TextChannel):
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

            return message


def setup(bot):
    bot.add_cog(Emotes(bot))
