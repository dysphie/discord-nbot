import discord
from discord.ext import commands
import os
from geopy.geocoders import Nominatim


class WeatherOld(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.geolocator = Nominatim(user_agent="nbot")
        self.locations = bot.db['locations']
        self.session = bot.session
        try:
            self.api_key = os.environ['DARKSKY_API_KEY']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        return (celsius * 9 / 5) + 32

    @staticmethod
    def kmh_to_mph(kmh: float) -> float:
        return kmh * 0.621371

    @commands.command(aliases=['tempold', 'wold'])
    async def weatherold(self, ctx, *, args=None):

        latitude = None
        longitude = None
        address = None

        if not args:
            result = await self.locations.find_one({'_id': ctx.author.id})
            if not result:
                await ctx.send('No location specified and no location saved')
                return

            latitude = result['lat']
            longitude = result['long']
            address = result['addr']

        else:
            location = self.geolocator.geocode(args)
            if not location:
                await ctx.send('Unknown location')
                return

            latitude = location.latitude
            longitude = location.longitude
            address = location.address

        url = f'https://api.darksky.net/forecast/{self.api_key}/{latitude},{longitude}?units=ca'
        print(url)
        async with self.session.get(url) as resp:
            data = await resp.json()

        summary = data['currently']['summary']
        temp = round(data['currently']['temperature'])
        temp_f = round(self.celsius_to_fahrenheit(temp))
        apparent_temp = round(data['currently']['apparentTemperature'])
        apparent_temp_f = round(self.celsius_to_fahrenheit(apparent_temp))
        humidity_pct = round(data['currently']['humidity'] * 100)
        wind_speed_kmh = round(data['currently']['windSpeed'], 2)
        wind_speed_mph = round(self.kmh_to_mph(wind_speed_kmh), 2)
        hourly_prediction = data['hourly']['summary']

        # Announce to channel
        embed = discord.Embed(description=f'{summary} ･ _{hourly_prediction}_', color=0x7fffd4)
        embed.add_field(
            inline=True, name='🌡️ **Temp**',
            value=f'{temp}°C _(feels like {apparent_temp}°C)_\n{temp_f}°F _(feels like {apparent_temp_f}°F)_')

        embed.add_field(inline=True, name='💧 **Humidity**', value=f'{humidity_pct}%')
        embed.add_field(inline=True, name="🍃 **Wind**", value=f'{wind_speed_kmh} km/h\n{wind_speed_mph} mph')
        embed.set_footer(text=address)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(WeatherOld(bot))