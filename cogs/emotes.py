import re

import discord
from discord import HTTPException
from discord.ext import commands
from pymongo.errors import DuplicateKeyError

INVISIBLE_CHAR = '\u17B5'
EMOTE_PATTERN = re.compile(r'\$([^\s$]+)')


class Emotes(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.emotedb = bot.db['new_emotes']  # TODO: Fetch from config
        self.session = bot.session
        self.storage = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.storage = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        prefixed = EMOTE_PATTERN.findall(message.content)
        to_delete = []

        pipe = [
            {'$match': {'name': {'$in': prefixed}}},
            {'$project': {'name': 1, 'url': 1, 'length': {'$strLenCP': '$name'}}},
            {'$sort': {'length': -1}}
        ]

        async for doc in self.emotedb.aggregate(pipeline=pipe):
            name = doc['name']
            emote = await self.create_emote_from_url(name, doc['url'])
            if emote:
                to_delete.append(emote)
                message.content = message.content.replace(f"${name}", str(emote))

        if to_delete:
            to_delete.append(message)

            sent = await self.impersonate(message.author, message.content, message.channel)
            if sent:
                for trash in to_delete:
                    await trash.delete()

    async def create_emote_from_url(self, name: str, url: str):
        async with self.session.get(url) as response:
            image_bytes = await response.read()
            try:
                emote = await self.storage.create_custom_emoji(name=name, image=image_bytes)
            except HTTPException as e:
                pass
            else:
                return emote

    @commands.command()
    async def add(self, ctx, name, url):
        try:
            emote = await self.create_emote_from_url(name, url)
        except Exception as e:
            await ctx.send('Discord rejected the emote (too big?)')
        else:
            try:
                await self.bot.emotedb.insert_one({
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
        deleted = await self.bot.emotesdb.find_one_and_delete({'name': name, 'owner': ctx.author.id})
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





