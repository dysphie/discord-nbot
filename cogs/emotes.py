import discord
from discord.ext import commands
import re
import aiohttp
from pymongo.errors import DuplicateKeyError

PAT_CUSTOM_EMOTE = re.compile(r'\$([a-zA-Z0-9]+)')

# cogs must now subclass commands.Cog
class Emotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    @commands.Cog.listener()
    async def on_ready(self):
        self.storage = self.bot.get_guild(self.bot.cfg['emote_storage_guild'])

    # listeners now must have a decorator
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        prefixed = re.findall(PAT_CUSTOM_EMOTE, message.content)

        to_delete = []
        #to_delete = [message]
        async for doc in self.bot.db.emotes.find({'name': {'$in': prefixed}}):
            name = doc['name']
            emote = await self.create_emote_from_url(self.storage, name, doc['url'])
            to_delete.append(emote)
            message.content = message.content.replace(f"${name}", str(emote))

        #if len(to_delete) < 2:
        #    return

        try:
            await impersonate(message.author, message.content, message.channel)
        except:
            pass
        finally:
            await message.delete()
            await asyncio.sleep(5)
            for item in to_delete:
                await item.delete()

            # TODO: Why are these getting deleted before the msg is sent?
            # for item in to_delete:
            #    await item.delete()

    @staticmethod
    async def create_emote_from_url(guild: discord.Guild, name: str, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                image_bytes = await response.read()
                emote = await guild.create_custom_emoji(name=name, image=image_bytes)
                return emote

    @commands.command()
    async def echo(self, ctx, *, message):
        await ctx.send(message)

    @commands.command()
    async def add(self, ctx, name, url):
        try:
            emote = await self.create_emote_from_url(ctx.guild, name, url)
        except discord.HTTPException as e:
            ctx.send(e)
        else:
            try:
                result = await self.bot.db.emotes.insert_one({
                    'owner': ctx.author.id,
                    'name': name,
                    'url': str(emote.url)
                })
            except DuplicateKeyError:
                await ctx.send(f'Emote with that name already exists')
            else:
                await ctx.send(f'Added emote `${name}`')
            finally:
                await emote.delete()

    @commands.command()
    async def remove(self, ctx, name):
        doc = await self.bot.db.emotes.find_one_and_delete({'name': name, ctx.author: ctx.author.id})
        await ctx.send(doc)


def setup(bot):
    bot.add_cog(Emotes(bot))


INVISIBLE_CHAR = '\u17B5'

async def impersonate(member: discord.Member, message: str, channel: discord.TextChannel):
    """Post a webhook that looks like a message sent by the user."""

    # Webhook usernames require at least 2 characters
    username = member.display_name.ljust(2, INVISIBLE_CHAR)

    webhook = await channel.create_webhook(name='temp')
    await webhook.send(
        username=username,
        content=message,
        avatar_url=member.avatar_url
    )
    await webhook.delete()

