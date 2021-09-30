import os
import discord
from discord import Option, slash_command
from discord.ext import commands

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

    @slash_command(name="complete", description="Have the bot autocomplete this message.")
    async def complete(self,
                       ctx,
                       prompt: Option(str, "Text to autocomplete")):

        base = f'**{discord.utils.escape_markdown(prompt)}**'
        await ctx.defer()
        json = {
            'prompt': prompt,
            'max_tokens': 80,
            'temperature': 0.9,
        }
        async with self.session.post(URL, headers=HEADERS, json=json) as r:
            result = await r.json()
            error = result.get('error')
            if error:
                await ctx.send(f"<:pepeLaugh:665663440014147616> {error['message']}")
            else:
                final = base + result['choices'][0]['text']
                await ctx.send(truncate_string(final))


def setup(bot):
    bot.add_cog(OpenAI(bot))
