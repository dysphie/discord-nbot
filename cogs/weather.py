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

    @commands.command(aliases=['temp'])
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

        url = f'https://api.darksky.net/forecast/{self.api_key}/{latitude},{longitude}?units=ca'
        print(url)
        async with self.session.get(url) as resp:
            data = await resp.json()

        summary = data['currently']['summary']
        temp = data['currently']['temperature']
        humidity = data['currently']['humidity']
        wind_speed = data['currently']['windSpeed']
        pred = data['hourly']['summary']

        # Announce to channel
        embed = discord.Embed(description=f'{summary} ･ _{pred}_', color=0x7fffd4)
        embed.add_field(name='**:thermometer:️ Temp**', value=f'{int(temp)}°C ･ {int(temp * 1.8 + 32)}°F', inline=True)
        embed.add_field(name='💧 **Humidity**', value=f'{int(humidity * 100)}%', inline=True)
        embed.add_field(name="🍃 **Wind**", value=f'{wind_speed} km/h ･ {int(wind_speed * 0.621371)} mph', inline=True)
        embed.set_footer(text=address)
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
