import operator
from typing import Optional
from discord import Embed, Message, RawReactionActionEvent, InvalidData, NotFound, Forbidden, HTTPException, \
    TextChannel, Reaction
from discord.ext import commands
from pymongo.collection import Collection

from main import DiscordBot

# Star is special and always pins, other emotes require 3 reactions
STAR_EMOJI = '⭐'
MIN_REACTIONS = 4


class Starboard(commands.Cog):

    def __init__(self, bot):
        self.bot: DiscordBot = bot
        self.stardb: Collection = bot.db['starboard_test']
        self.starchannel: Optional[TextChannel] = None

    @commands.Cog.listener()
    async def on_ready(self):
        starboard_id = self.bot.cfg['starboard_channel']
        self.starchannel = self.bot.get_channel(starboard_id)
        if not self.starchannel:
            raise Exception(f"Couldn't find starboard channel with id {starboard_id}")

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        await self.on_message_reacted(payload)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        await self.on_message_reacted(payload)

    async def on_message_reacted(self, payload: RawReactionActionEvent):
        try:
            channel = await self.bot.fetch_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
        except (HTTPException, InvalidData, NotFound, Forbidden, InvalidData):
            return

        top_reaction = self.get_top_reaction(msg)
        starred = await self.get_starred_for_msg(msg)
        if starred is not None:
            if top_reaction is None:
                await starred.delete()
                await self.stardb.delete_one({'_id': msg.id})
            elif starred.embeds:
                embed = starred.embeds[0].copy()
                self.footer_from_reaction(embed, top_reaction)
                await starred.edit(embed=embed)
        elif top_reaction is not None:
            embed = Embed(description=msg.content, color=0xFFAC33)
            embed.set_author(name=msg.author.display_name, url=msg.jump_url, icon_url=msg.author.display_avatar.url)
            self.footer_from_reaction(embed, top_reaction)

            if len(msg.attachments) > 0 and 'image' in msg.attachments[0].content_type:
                embed.set_image(url=msg.attachments[0].url)

            starred = await self.starchannel.send(embed=embed)
            await self.stardb.insert_one({'_id': msg.id, 'star_id': starred.id})

    async def get_starred_for_msg(self, msg: Message) -> Optional[Message]:

        doc = await self.stardb.find_one({'_id': msg.id})
        if doc:
            try:
                starred = await self.starchannel.fetch_message(doc['star_id'])
            except (NotFound, Forbidden, HTTPException):
                pass
            else:
                return starred

    @staticmethod
    def footer_from_reaction(embed: Embed, reaction: Reaction):
        if reaction.is_custom_emoji():
            embed.set_footer(icon_url=reaction.emoji.url, text=f'{reaction.count}')
        else:
            embed.set_footer(text=f'{reaction.emoji} {reaction.count}')

    @staticmethod
    def get_top_reaction(msg: Message) -> Optional[Reaction]:
        if not msg.reactions:
            return None

        min_count = MIN_REACTIONS - 1
        best_reaction = None
        for r in msg.reactions:
            if r.emoji == '⭐' or r.count > min_count:
                min_count = r.count
                best_reaction = r

        return best_reaction


def setup(bot):
    bot.add_cog(Starboard(bot))
