import discord
from discord.ext import commands
import random
import os
from utils import clean
import aiohttp
from geopy.geocoders import Nominatim


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        try:
            self.api_key = os.environ['DARKSKY_API_KEY']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

    @commands.command(aliases=['temp'])
    async def weather(self, ctx, *, query):

        # Chance of snarky response
        if 'Cleverbot' in self.bot.cogs:
            if random.random() < self.bot.cfg['weather-cleverbot-chance']:
                async with ctx.typing():
                    query = f"What's the weather in {clean(query)}?"
                    response = clean(await self.bot.brain.ask(query))
                    if response:
                        await ctx.send(response)
                        return

        # Get actual weather
        geolocator = Nominatim()
        location = geolocator.geocode(query)
        if not location:
            await ctx.message.add_reaction("❌")
            return

        url = f'https://api.darksky.net/forecast/{self.api_key}/{location.latitude},{location.longitude}?units=ca'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        summary = data['currently']['summary']
        temp = data['currently']['temperature']
        humidity = data['currently']['humidity']
        wind_speed = data['currently']['windSpeed']
        pred = data['hourly']['summary']
        # map = f'http://www.google.com/maps/place/{location.latitude},{location.longitude}'

        # Announce to channel
        embed = discord.Embed(description=f'{summary} ･ _{pred}_', color=0x7fffd4)
        embed.add_field(name='**:thermometer:️ Temp**', value=f'{int(temp)}°C ･ {int(temp*1.8+32)}°F', inline=True)
        embed.add_field(name='💧 **Humidity**', value=f'{int(humidity*100)}%', inline=True)
        embed.add_field(name="🍃 **Wind**", value=f'{wind_speed} km/h ･ {int(wind_speed*0.621371)} mph', inline=True)
        embed.set_footer(text=location.address)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Weather(bot))
