import discord
from discord.ext import commands
import os
from geopy.geocoders import Nominatim


class Weather(commands.Cog):

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

    @commands.command(aliases=['temp', 'w'])
    async def weather(self, ctx, *, args=None):

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
        temp = data['currently']['temperature']
        temp_f = self.celsius_to_fahrenheit(temp)
        apparent_temp = data['currently']['apparentTemperature']
        apparent_temp_f = self.celsius_to_fahrenheit(apparent_temp)
        humidity_pct = data['currently']['humidity'] * 100
        wind_speed_kmh = data['currently']['windSpeed']
        wind_speed_mph = self.kmh_to_mph(wind_speed_kmh)
        hourly_prediction = data['hourly']['summary']

        # Announce to channel
        embed = discord.Embed(description=f'{summary} ･ _{hourly_prediction}_', color=0x7fffd4)
        embed.add_field(
            inline=True, name='🌡️ **Temp**',
            value=f'{temp}°C _(feels like {apparent_temp}°C)_\n{temp_f}°F _(feels like {apparent_temp_f}°F)_')

        embed.add_field(inline=True, name='💧 **Humidity**', value=f'{humidity_pct}%')
        embed.add_field(inline=True, name="🍃 **Wind**", value=f'{wind_speed_kmh} km/h\n{wind_speed_mph} mph')
        embed.set_footer(text=address)

        for alert in data['alerts']:
            embed.add_field(inline=True, name=alert['title'], value=alert['description'])

        await ctx.send(embed=embed)

    @commands.command(aliases=['setloc'])
    async def setlocation(self, ctx, *, args):

        location = self.geolocator.geocode(args)
        if not location:
            await ctx.send('Unknown location')
            return

        await self.locations.update_one(
            {'_id': ctx.author.id},
            {'$set': {
                'lat': location.latitude,
                'long': location.longitude,
                'addr': location.address
            }},
            upsert=True)

        await ctx.send(f'Set location to `{location.address}`')

    @commands.command(aliases=['removeloc'])
    async def removelocation(self, ctx):
        result = await self.locations.delete_many({'_id': ctx.author.id})
        await ctx.send('Location cleared')


def setup(bot):
    bot.add_cog(Weather(bot))
