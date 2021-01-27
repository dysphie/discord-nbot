import textwrap
import discord
from discord.ext import commands

class Starboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.stardb = bot.db.starboard
        self.starchannel = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.starchannel = self.bot.get_channel(self.bot.cfg['starboard_channel'])

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_add(self, payload):

        if self.starchannel is None or str(payload.emoji) != '⭐':
            return

        channel = await self.bot.fetch_channel(payload.channel_id)

        starred_data = await self.stardb.find_one({'_id': payload.message_id})
        if starred_data:
            starred = await self.starchannel.fetch_message(starred_data['star_id'])
            if starred:
                await self.increase_reactions(starred)
            return

        message = await channel.fetch_message(payload.message_id)
        if message:
            await self.star_message(message)

    async def star_message(self, message: discord.Message):

        username = message.author.display_name.ljust(2, '\u17B5')

        webhooks = await self.starchannel.webhooks()
        webhook = discord.utils.find(lambda m: m.user.id == self.bot.user.id, webhooks)
        if not webhook:
            webhook = await self.starchannel.create_webhook(name='Starboard')

        starred = await webhook.send(
            username=username,
            content=textwrap.shorten(message.content, width=2000, placeholder=" .."),
            files=[await a.to_file() for a in message.attachments],
            avatar_url=message.author.avatar_url,
            embed=discord.Embed(
                description=f'⭐ **1** - [Original]({message.jump_url})',
                color=0xFFAC33),
            wait=True
        )

        await self.stardb.insert_one({'_id': message.id, 'star_id': starred.id})

    @staticmethod
    async def increase_reactions(starred: discord.Message):
        pass # TODO

    # TODO: reaction remove


def setup(bot):
    bot.add_cog(Starboard(bot))
