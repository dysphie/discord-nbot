from discord import Embed
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

    async def star_message(self, message):

        embed = Embed(description=message.content)
        embed.set_author(name='Content', url=message.jump_url)
        embed.add_field(name='Author', value=message.author.mention)
        embed.add_field(name='Channel', value=message.channel.mention)
        embed.set_footer(text='1 gay bean')
        starred = await self.starchannel.send(embed=embed)

        await self.stardb.insert_one({'_id': message.id, 'star_id': starred.id})

    @staticmethod
    async def increase_reactions(starred):
        embedict = starred.embeds[0].copy().to_dict()
        print(embedict)
        embedict['footer']['text'] = 'many gay bean'
        embed = Embed.from_dict(embedict)
        await starred.edit(embed=embed)

    # TODO: reaction remove


def setup(bot):
    bot.add_cog(Starboard(bot))
