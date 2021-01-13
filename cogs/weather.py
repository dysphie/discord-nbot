import aiohttp
import discord
from discord.ext import commands
import os
from geopy.geocoders import Nominatim
import arrow

weather_codes = {
    "0": "Unknown",
    "1000": "Clear",
    "1001": "Cloudy",
    "1100": "Mostly Clear",
    "1101": "Partly Cloudy",
    "1102": "Mostly Cloudy",
    "2000": "Fog",
    "2100": "Light Fog",
    "3000": "Light Wind",
    "3001": "Wind",
    "3002": "Strong Wind",
    "4000": "Drizzle",
    "4001": "Rain",
    "4200": "Light Rain",
    "4201": "Heavy Rain",
    "5000": "Snow",
    "5001": "Flurries",
    "5100": "Light Snow",
    "5101": "Heavy Snow",
    "6000": "Freezing Drizzle",
    "6001": "Freezing Rain",
    "6200": "Light Freezing Rain",
    "6201": "Heavy Freezing Rain",
    "7000": "Ice Pellets",
    "7101": "Heavy Ice Pellets",
    "7102": "Light Ice Pellets",
    "8000": "Thunderstorm"
}


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.weather_guild = None
        self.geolocator = Nominatim(user_agent="nbot")
        self.locations = bot.db['locations']
        self.session = bot.session

        try:
            self.api_key = os.environ['CLIMACELL_API_KEY']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

    @commands.Cog.listener()
    async def on_ready(self):
        self.weather_guild = self.bot.get_guild(759525750201909319)

    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        return (celsius * 9 / 5) + 32

    def get_emote_str_from_weather_code(self, code, night):
        text = weather_codes.get(str(code))
        if text:
            # HACKHACK: Patch icons that have day/night variants
            # TODO: Less hacky way to do this?
            if text in ['Partly Cloudy', 'Mostly Clear', 'Clear']:
                text += 'Night' if night else 'Day'

            text = text.replace(" ", "")
            emote = discord.utils.find(lambda e: e.name == text, self.weather_guild.emojis)
            if emote:
                return str(emote)
            else:
                print(f'Couldnt find emote named {text}')
        else:
            print(f'Code not in weather_codes: {code}')
        return '🍌'  # no results return banan

    @commands.command(aliases=['temp', 'w'])
    async def weather(self, ctx, *, args=None):

        if not args:
            result = await self.locations.find_one({'_id': ctx.author.id})
            if not result:
                await ctx.error('No location specified and no location saved')
                return

            latitude = result['lat']
            longitude = result['long']
            address = result['addr']

        else:
            location = self.geolocator.geocode(args)
            if not location:
                await ctx.error('Unknown location')
                return

            latitude = location.latitude
            longitude = location.longitude
            address = location.address

        url = "https://data.climacell.co/v4/timelines"
        querystring = {"apikey": self.api_key}
        headers = {"Content-Type": "application/json"}
        payload = {
            "fields": ["temperature", "humidity", "windSpeed", "weatherCode", "sunsetTime", "sunriseTime"],
            "timesteps": ["1h", "1d"],
            "location": f"{latitude}, {longitude}"
        }

        async with self.session.post(url, json=payload, headers=headers, params=querystring) as r:
            data = await r.json()
            sunset = data['data']['timelines'][1]['intervals'][0]['values']['sunsetTime']
            sunrise = data['data']['timelines'][1]['intervals'][0]['values']['sunriseTime']
            # print(f'sun rises at {arrow.get(sunrise).humanize()}')  # TODO: wtf these are wrong?
            # print(f'sun sets at {arrow.get(sunset).humanize()}')

            now_field = ''
            forecast_field = ''

            num_rows = 4
            hour_gap = 2
            for i in range(0, num_rows * hour_gap, hour_gap):

                temp = data['data']['timelines'][0]['intervals'][i]['values']['temperature']
                temp_f = self.celsius_to_fahrenheit(temp)
                weather_code = data['data']['timelines'][0]['intervals'][i]['values']['weatherCode']
                time = data['data']['timelines'][0]['intervals'][i]['startTime']
                is_night = sunset < time < sunrise

                weather_icon = self.get_emote_str_from_weather_code(weather_code, night=is_night)

                if i == 0:  # Now
                    humidity = data['data']['timelines'][0]['intervals'][i]['values']['humidity']
                    wind = data['data']['timelines'][0]['intervals'][i]['values']['windSpeed']
                    now_field = f"""
                                {weather_icon} **{round(temp)}**°C / **{round(temp_f)}**°F 
                                💧 **{humidity}**%
                                🍃 **{wind}** m/s"""
                else:
                    hours_from_now = arrow.get(time).humanize()
                    forecast_field += f'{weather_icon} **{round(temp)}**°C / **{round(temp_f)}**°F - {hours_from_now}\n'

            embed = discord.Embed(color=0x7fffd4)
            embed.add_field(inline=True, name='Now', value=now_field)
            embed.add_field(inline=True, name='Forecast', value=forecast_field)
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
