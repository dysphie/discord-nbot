import os
from pprint import pprint

import discord
from discord.ext import commands
from discord_slash import SlashCommandOptionType, cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option

from cogs.utils import truncate_string

URL = 'https://api.openai.com/v1/engines/davinci/completions'
HEADERS = {
    'content-type': 'application/json',
    'authorization': f'Bearer {os.environ["OPENAI_API_KEY"]}'
}


class OpenAI(commands.Cog, name="OpenAI"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @cog_ext.cog_slash(name="complete",
                       description="Have the bot autocomplete this message.",
                       options=[
                           create_option(
                               name="prompt",
                               description="Text to autocomplete",
                               option_type=SlashCommandOptionType.STRING,
                               required=True
                           )
                       ]
                       )
    # @commands.command(aliases=['autocomplete', 'ac', 'imagine', 'prompt'])
    async def complete(self, ctx: SlashContext, prompt: str = None):

        base = f'**{discord.utils.escape_markdown(prompt)}**'

        await ctx.defer()
        json = {
            'prompt': prompt,
            'max_tokens': 80,
            'temperature': 0.9,
        }
        async with self.session.post(URL, headers=HEADERS, json=json) as r:
            result = await r.json()
            final = base + result['choices'][0]['text']
            await ctx.send(truncate_string(final))


def setup(bot):
    bot.add_cog(OpenAI(bot))
