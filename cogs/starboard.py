import textwrap
from discord import RawReactionActionEvent, Message, Embed, utils, NotFound, Forbidden, HTTPException
from discord.ext import commands

STAR_EMOJI = '⭐'


class Starboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.stardb = bot.db.starboard
        self.starchannel = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.starchannel = self.bot.get_channel(self.bot.cfg['starboard_channel'])
        if not self.starchannel:
            raise Exception('Invalid starboard channel')

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        await self.on_raw_reaction_event(payload)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        await self.on_raw_reaction_event(payload)

    async def on_raw_reaction_event(self, payload: RawReactionActionEvent):

        if str(payload.emoji) != STAR_EMOJI:
            return

        channel = await self.bot.fetch_channel(payload.channel_id)
        original = await channel.fetch_message(payload.message_id)

        if original.author.id == payload.user_id:  # No self starring!
            return

        already_starred = await self.stardb.find_one({'_id': payload.message_id})
        if already_starred:
            try:
                starred = await self.starchannel.fetch_message(already_starred['star_id'])
            except (NotFound, Forbidden, HTTPException):
                pass
            else:
                await self.update_starred(starred, original)
        else:
            await self.star_message(original)

    async def star_message(self, original: Message):

        # Find suitable webhook transport
        starred = await self.starchannel.send(
            reference=original,
            mention_author=False,
            content=self.generate_star_stats(original)
        )

        if starred:
            await self.stardb.insert_one({'_id': original.id, 'star_id': starred.id})

    async def update_starred(self, starred: Message, original: Message):

        num_stars = self.count_stars(original)
        print(num_stars)
        if num_stars <= 0:
            await starred.delete()
            await self.stardb.delete_one({'_id': original.id})
        else:
            new_content = self.generate_star_stats(original, stars_override=num_stars)
            await starred.edit(content=new_content)

    def generate_star_stats(self, message: Message, stars_override=None) -> str:
        num_stars = stars_override or self.count_stars(message)
        return f'⭐ **{num_stars}**'

    @staticmethod
    def count_stars(message: Message):
        for reaction in message.reactions:
            if reaction.emoji == STAR_EMOJI:
                return reaction.count
        return 0


def setup(bot):
    bot.add_cog(Starboard(bot))
