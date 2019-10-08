# TODO:
#  Overall cleanup and bug fixing
#  Merge EmotesCache and UsersCache into single object
#  Unify URL and file fetching

from collections import defaultdict
import motor.motor_asyncio
from aiohttp import ClientSession
from discord.ext import commands
from pymongo import ReturnDocument
from pymongo.errors import ConnectionFailure
from aesthetics import *

FFZ_API = 'https://api.frankerfacez.com/v1'


async def url_to_json(url: str, params: dict):
    async with ClientSession() as session:
        async with session.get(url, params=params) as r:
            if r.status == 200:
                data = await r.json()
                return data


async def url_to_file(url: str):
    async with ClientSession() as session:
        async with session.get(url) as r:
            if r.status == 200:
                data = await r.read()
                return data


async def send_as(member: discord.Member, message: str, channel: discord.TextChannel):
    webhook = await channel.create_webhook(name='temp')
    await webhook.send(
        username=member.display_name,
        content=message,
        avatar_url=member.avatar_url
    )
    await webhook.delete()


class EmotesCache:

    def __init__(self, emotes_remote: motor.motor_asyncio.AsyncIOMotorCollection):
        self.emotes_remote = emotes_remote
        self.emotes = {}

    async def populate(self):
        async for document in self.emotes_remote.find():
            self.emotes[document['_id']] = document['ffz_id']


class UsersCache:

    def __init__(self, users_remote: motor.motor_asyncio.AsyncIOMotorCollection):
        self.users_remote = users_remote
        self.users = defaultdict(lambda: [set(), 0])

    async def populate(self):
        async for user in self.users_remote.find():
            self.update_user(user)

    def update_user(self, document: dict):
        user_id = document.get('_id')
        if not user_id:
            return

        if document.get('enable'):
            banned_emotes = document.get('banned_emotes', [])
            require_colons = document.get('require_colons', False)
            self.users[user_id] = [banned_emotes, require_colons]
        else:
            self.users.pop(user_id, None)


class FFZ(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.users = bot.db['ffz.users']
        self.emotes = bot.db['ffz.emotes']
        self.users_cache = UsersCache(self.users)
        self.emotes_cache = EmotesCache(self.emotes)
        bot.loop.create_task(self.users_cache.populate())
        bot.loop.create_task(self.emotes_cache.populate())

    @commands.Cog.listener()
    async def on_message(self, message):

        # TODO: Hacky hack, do properly
        if message.content.startswith('.ffz'):
            return

        # Bail if sender hasn't opted in
        if message.author.id not in self.users_cache.users.keys():
            return

        # Identify valid FFZ emotes
        words = message.clean_content.split()
        wanted_emotes = set(w for w in words if w in self.emotes_cache.emotes.keys())
        for e in wanted_emotes:
            if e in self.users_cache.users[message.author.id][0]:
                wanted_emotes.remove(e)

        # Filter out emotes blacklisted by the sender, bail if no emotes left
        wanted_emotes = [i for i in wanted_emotes if i not in self.users_cache.users[message.author.id]]
        if not wanted_emotes:
            return

        # Upload emotes to server and remember them
        dumpster = [message]
        for i in wanted_emotes:
            emote = await self.create_emote_from_ffz_name(i, message.guild)
            emote and dumpster.append(emote)
            message.content = message.content.replace(i, str(emote))

        # Repost message with all emotes replaced. Delete uploaded emotes
        await send_as(message.author, message.content, message.channel)

        # TODO: Don't wait arbitrarily. Do proper callback
        await asyncio.sleep(2)
        for item in dumpster:
            await item.delete()

    @commands.group(invoke_without_command=False)
    async def ffz(self, ctx):
        pass

    @ffz.command(aliases=['e', 'on'])
    async def enable(self, ctx):
        if ctx.author.id in self.users_cache.users.keys():
            await send_info(ctx, 'Emote parsing is already turned on.')
            return

        try:
            user_data = await self.users_cache.users_remote.find_one_and_update(
                {'_id': ctx.author.id},
                {'$set': {'enable': True}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except ConnectionFailure:
            await send_error(ctx, 'Database unreachable, try again later')
        else:
            self.users_cache.update_user(user_data)
            await send_success(ctx, 'Enabled emote parsing for your user')

    @ffz.command(aliases=['d', 'off'])
    async def disable(self, ctx):
        if ctx.author.id not in self.users_cache.users.keys():
            await send_info(ctx, 'Emote parsing is already turned off.')
            return

        try:
            user_data = await self.users_cache.users_remote.find_one_and_update(
                {'_id': ctx.author.id},
                {'$set': {'enable': False}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except ConnectionFailure:
            await send_error(ctx, 'Database unreachable, try again later')
        else:
            self.users_cache.update_user(user_data)
            await send_success(ctx, 'Disabled emote parsing for your user')

    @ffz.command(aliases=['b', 'ban', 'block'])
    async def ban_emotes(self, ctx, *, query: str):
        emotes = [e for e in query.split() if e in self.emotes_cache.emotes.keys()]
        if not emotes:
            await send_warning(ctx, 'Found no valid emotes to ban. Check your capitalization.')
            return

        try:
            user_data = await self.users.find_one_and_update(
                {'_id': ctx.author.id},
                {'$addToSet': {'banned_emotes': {'$each': emotes}}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except ConnectionError:
            await send_error(ctx, "Couldn't connect to database, try again later")
        else:
            self.users_cache.update_user(user_data)
            await send_success(ctx, f"No longer parsing {create_human_list(emotes)} for your user.")

    @ffz.command(aliases=['u', 'unban', 'unblock'])
    async def unban_emotes(self, ctx, *, query: str):
        emotes = [e for e in query.split()]
        if not emotes:
            await ctx.send('Found no valid emotes')
            return

        try:
            user_data = await self.users.find_one_and_update(
                {'_id': ctx.author.id},
                {'$pull': {'banned_emotes': {'$in': emotes}}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except ConnectionError:
            await send_error(ctx, "Couldn't connect to database, try again later")
        else:
            self.users_cache.update_user(user_data)
            await send_success(ctx, f'No longer ignoring {create_human_list(emotes)} for your user.')

    @ffz.command(aliases=['tc', 'toggle colons'])
    async def toggle_require_colons(self, ctx):
        try:
            user_data = await self.users.find_one_and_update(
                {"_id": ctx.author.id},
                {"$bit": {"require_colons": {"xor": int(True)}}},
                upsert=True, return_document=ReturnDocument.AFTER)

        except ConnectionError:
            await send_warning(ctx, "Couldn't connect to database, try again later")
        else:
            self.users_cache.update_user(user_data)
            await send_success(ctx, f"{'En' if user_data['require_colons'] else 'Dis'}"
                               f"abled colon requirement for your user.")

    async def create_emote_from_ffz_name(self, name: str, guild):
        url = f'https://cdn.frankerfacez.com/emoticon/{self.emotes_cache.emotes[name]}/1'
        image = await url_to_file(url)
        emote = await guild.create_custom_emoji(name=name, image=image)
        return emote


def setup(bot):
    bot.add_cog(FFZ(bot))
