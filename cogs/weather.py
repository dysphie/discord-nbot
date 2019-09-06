import discord
from discord.ext import commands
import random
import os
from utils import clean
import aiohttp


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        try:
            self.wapi = os.environ['OPENWEATHER_API']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

    @commands.command(aliases=['temp'])
    async def weather(self, ctx, *, location):

        if('Cleverbot' in self.bot.cogs) and self.bot.brain:
            if random.random() < self.bot.cfg['weather-cleverbot-chance']:
                async with ctx.typing():
                    query = f"What's the weather in {clean(location)}?"
                    response = clean(await self.bot.brain.ask(query))
                    if response:
                        await ctx.send(response)
                        return

        w = await self.get_weather(location)

        if w:
            temperature = w['main']['temp']
            details = w['weather'][0]['description']
            humidity = w['main']['humidity']
            wind_speed = w['wind']['speed']
            country = w['sys']['country']
            city = w['name']

            embed = discord.Embed(
                title=f'{city}, {country}',
                description=f'{int(temperature)}°C, {details[0].upper() + details[1:]}')

            embed.add_field(name="Humidity", value=f'{humidity}%', inline=True)
            embed.add_field(name="Wind speed", value=f'{wind_speed} km/h', inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Not found")

    async def get_weather(self, location):
        api_url = "http://api.openweathermap.org/data/2.5/weather?q="
        parameters = "{}&units=metric&appid={}".format(
            location, self.wapi)

        async with aiohttp.ClientSession() as session:
            response = await session.get(api_url + parameters)
            json = await response.json()
            print(json)
            return json


def setup(bot):
    bot.add_cog(Weather(bot))
