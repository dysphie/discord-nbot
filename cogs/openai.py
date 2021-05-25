import os
import openai
from discord.ext import commands

openai.api_key = os.getenv('OPENAI_API_KEY')


class OpenAITest(commands.Cog, name="OpenAI Tests"):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def giveme(self, ctx, *, message):
        response = openai.Completion.create(
            engine="davinci-instruct-beta",
            prompt=message,
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            frequency_penalty=0.5,
            presence_penalty=0
        )
        await ctx.send(response['choices'][0]['text'])

    @commands.command()
    async def imagine(self, ctx, *, message):
        response = openai.Completion.create(
            engine="davinci",
            prompt=message,
            temperature=0.7,
            max_tokens=512,
            top_p=1,
            frequency_penalty=0.5,
            presence_penalty=0
        )
        await ctx.send(response['choices'][0]['text'])


def setup(bot):
    bot.add_cog(OpenAITest(bot))
