import arrow
import discord
import youtube_dl
from discord.ext import commands
from discord_slash import SlashCommandOptionType, cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option


class Twitter(commands.Cog, name="OpenAI"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @cog_ext.cog_slash(
        guild_ids=[719448049981849620, 336213135193145344],
        name="twitter",
        description="Embeds twitter videos properly",
        options=[
            create_option(
                name="url",
                description="URL to a tweet",
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ]
    )
    async def twitter(self, ctx: SlashContext, url: str = None):
        await ctx.defer()

        with youtube_dl.YoutubeDL({}) as ydl:
            result = ydl.extract_info(url, download=False)

            url = result.get('url', None)
            author_name = result.get('uploader')
            author_handle = result.get('uploader_id')
            author_full = f'{author_name} (@{author_handle})'
            author_url = result.get('uploader_url')

            description = result.get('description', ' ')

            retweets = result.get('repost_count', 0)
            likes = result.get('like_count', 0)
            timestamp = result.get('timestamp')

            embed = discord.Embed(color=0x1DA0F2, description=description)
            embed.add_field(inline=True, name='Retweets', value=retweets)
            embed.add_field(inline=True, name='Likes', value=likes)
            embed.set_author(name=author_full, url=author_url)
            embed.set_footer(text=arrow.get(timestamp).humanize())

            await ctx.send(embed=embed)
            await ctx.channel.send(url)


def setup(bot):
    bot.add_cog(Twitter(bot))
