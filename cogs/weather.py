import discord
from discord import Option, slash_command
from discord.ext import commands
import os
from geopy.geocoders import Nominatim
import arrow

# as seen in https://docs.tomorrow.io/reference/data-layers-core

precip_descs = {
    "0": "N/A",
    "1": "Rain",
    "2": "Snow",
    "3": "Freezing Rain",
    "4": "Ice Pellets"
}

weather_descs = {
    "weatherCodeDay": {
        "0": "Unknown",
        "10000": "Clear, Sunny",
        "11000": "Mostly Clear",
        "11010": "Partly Cloudy",
        "11020": "Mostly Cloudy",
        "10010": "Cloudy",
        "11030": "Partly Cloudy and Mostly Clear",
        "21000": "Light Fog",
        "21010": "Mostly Clear and Light Fog",
        "21020": "Partly Cloudy and Light Fog",
        "21030": "Mostly Cloudy and Light Fog",
        "21060": "Mostly Clear and Fog",
        "21070": "Partly Cloudy and Fog",
        "21080": "Mostly Cloudy and Fog",
        "20000": "Fog",
        "42040": "Partly Cloudy and Drizzle",
        "42030": "Mostly Clear and Drizzle",
        "42050": "Mostly Cloudy and Drizzle",
        "40000": "Drizzle",
        "42000": "Light Rain",
        "42130": "Mostly Clear and Light Rain",
        "42140": "Partly Cloudy and Light Rain",
        "42150": "Mostly Cloudy and Light Rain",
        "42090": "Mostly Clear and Rain",
        "42080": "Partly Cloudy and Rain",
        "42100": "Mostly Cloudy and Rain",
        "40010": "Rain",
        "42110": "Mostly Clear and Heavy Rain",
        "42020": "Partly Cloudy and Heavy Rain",
        "42120": "Mostly Cloudy and Heavy Rain",
        "42010": "Heavy Rain",
        "51150": "Mostly Clear and Flurries",
        "51160": "Partly Cloudy and Flurries",
        "51170": "Mostly Cloudy and Flurries",
        "50010": "Flurries",
        "51000": "Light Snow",
        "51020": "Mostly Clear and Light Snow",
        "51030": "Partly Cloudy and Light Snow",
        "51040": "Mostly Cloudy and Light Snow",
        "51220": "Drizzle and Light Snow",
        "51050": "Mostly Clear and Snow",
        "51060": "Partly Cloudy and Snow",
        "51070": "Mostly Cloudy and Snow",
        "50000": "Snow",
        "51010": "Heavy Snow",
        "51190": "Mostly Clear and Heavy Snow",
        "51200": "Partly Cloudy and Heavy Snow",
        "51210": "Mostly Cloudy and Heavy Snow",
        "51100": "Drizzle and Snow",
        "51080": "Rain and Snow",
        "51140": "Snow and Freezing Rain",
        "51120": "Snow and Ice Pellets",
        "60000": "Freezing Drizzle",
        "60030": "Mostly Clear and Freezing drizzle",
        "60020": "Partly Cloudy and Freezing drizzle",
        "60040": "Mostly Cloudy and Freezing drizzle",
        "62040": "Drizzle and Freezing Drizzle",
        "62060": "Light Rain and Freezing Drizzle",
        "62050": "Mostly Clear and Light Freezing Rain",
        "62030": "Partly Cloudy and Light Freezing Rain",
        "62090": "Mostly Cloudy and Light Freezing Rain",
        "62000": "Light Freezing Rain",
        "62130": "Mostly Clear and Freezing Rain",
        "62140": "Partly Cloudy and Freezing Rain",
        "62150": "Mostly Cloudy and Freezing Rain",
        "60010": "Freezing Rain",
        "62120": "Drizzle and Freezing Rain",
        "62200": "Light Rain and Freezing Rain",
        "62220": "Rain and Freezing Rain",
        "62070": "Mostly Clear and Heavy Freezing Rain",
        "62020": "Partly Cloudy and Heavy Freezing Rain",
        "62080": "Mostly Cloudy and Heavy Freezing Rain",
        "62010": "Heavy Freezing Rain",
        "71100": "Mostly Clear and Light Ice Pellets",
        "71110": "Partly Cloudy and Light Ice Pellets",
        "71120": "Mostly Cloudy and Light Ice Pellets",
        "71020": "Light Ice Pellets",
        "71080": "Mostly Clear and Ice Pellets",
        "71070": "Partly Cloudy and Ice Pellets",
        "71090": "Mostly Cloudy and Ice Pellets",
        "70000": "Ice Pellets",
        "71050": "Drizzle and Ice Pellets",
        "71060": "Freezing Rain and Ice Pellets",
        "71150": "Light Rain and Ice Pellets",
        "71170": "Rain and Ice Pellets",
        "71030": "Freezing Rain and Heavy Ice Pellets",
        "71130": "Mostly Clear and Heavy Ice Pellets",
        "71140": "Partly Cloudy and Heavy Ice Pellets",
        "71160": "Mostly Cloudy and Heavy Ice Pellets",
        "71010": "Heavy Ice Pellets",
        "80010": "Mostly Clear and Thunderstorm",
        "80030": "Partly Cloudy and Thunderstorm",
        "80020": "Mostly Cloudy and Thunderstorm",
        "80000": "Thunderstorm"
    },

    "weatherCodeNight": {
        "0": "Unknown",
        "10001": "Clear, Sunny",
        "11001": "Mostly Clear",
        "11011": "Partly Cloudy",
        "11021": "Mostly Cloudy",
        "10011": "Cloudy",
        "11031": "Partly Cloudy and Mostly Clear",
        "21001": "Light Fog",
        "21011": "Mostly Clear and Light Fog",
        "21021": "Partly Cloudy and Light Fog",
        "21031": "Mostly Cloudy and Light Fog",
        "21061": "Mostly Clear and Fog",
        "21071": "Partly Cloudy and Fog",
        "21081": "Mostly Cloudy and Fog",
        "20001": "Fog",
        "42041": "Partly Cloudy and Drizzle",
        "42031": "Mostly Clear and Drizzle",
        "42051": "Mostly Cloudy and Drizzle",
        "40001": "Drizzle",
        "42001": "Light Rain",
        "42131": "Mostly Clear and Light Rain",
        "42141": "Partly Cloudy and Light Rain",
        "42151": "Mostly Cloudy and Light Rain",
        "42091": "Mostly Clear and Rain",
        "42081": "Partly Cloudy and Rain",
        "42101": "Mostly Cloudy and Rain",
        "40011": "Rain",
        "42111": "Mostly Clear and Heavy Rain",
        "42021": "Partly Cloudy and Heavy Rain",
        "42121": "Mostly Cloudy and Heavy Rain",
        "42011": "Heavy Rain",
        "51151": "Mostly Clear and Flurries",
        "51161": "Partly Cloudy and Flurries",
        "51171": "Mostly Cloudy and Flurries",
        "50011": "Flurries",
        "51001": "Light Snow",
        "51021": "Mostly Clear and Light Snow",
        "51031": "Partly Cloudy and Light Snow",
        "51041": "Mostly Cloudy and Light Snow",
        "51221": "Drizzle and Light Snow",
        "51051": "Mostly Clear and Snow",
        "51061": "Partly Cloudy and Snow",
        "51071": "Mostly Cloudy and Snow",
        "50001": "Snow",
        "51011": "Heavy Snow",
        "51191": "Mostly Clear and Heavy Snow",
        "51201": "Partly Cloudy and Heavy Snow",
        "51211": "Mostly Cloudy and Heavy Snow",
        "51101": "Drizzle and Snow",
        "51081": "Rain and Snow",
        "51141": "Snow and Freezing Rain",
        "51121": "Snow and Ice Pellets",
        "60001": "Freezing Drizzle",
        "60031": "Mostly Clear and Freezing drizzle",
        "60021": "Partly Cloudy and Freezing drizzle",
        "60041": "Mostly Cloudy and Freezing drizzle",
        "62041": "Drizzle and Freezing Drizzle",
        "62061": "Light Rain and Freezing Drizzle",
        "62051": "Mostly Clear and Light Freezing Rain",
        "62031": "Partly cloudy and Light Freezing Rain",
        "62091": "Mostly Cloudy and Light Freezing Rain",
        "62001": "Light Freezing Rain",
        "62131": "Mostly Clear and Freezing Rain",
        "62141": "Partly Cloudy and Freezing Rain",
        "62151": "Mostly Cloudy and Freezing Rain",
        "60011": "Freezing Rain",
        "62121": "Drizzle and Freezing Rain",
        "62201": "Light Rain and Freezing Rain",
        "62221": "Rain and Freezing Rain",
        "62071": "Mostly Clear and Heavy Freezing Rain",
        "62021": "Partly Cloudy and Heavy Freezing Rain",
        "62081": "Mostly Cloudy and Heavy Freezing Rain",
        "62011": "Heavy Freezing Rain",
        "71101": "Mostly Clear and Light Ice Pellets",
        "71111": "Partly Cloudy and Light Ice Pellets",
        "71121": "Mostly Cloudy and Light Ice Pellets",
        "71021": "Light Ice Pellets",
        "71081": "Mostly Clear and Ice Pellets",
        "71071": "Partly Cloudy and Ice Pellets",
        "71091": "Mostly Cloudy and Ice Pellets",
        "70001": "Ice Pellets",
        "71051": "Drizzle and Ice Pellets",
        "71061": "Freezing Rain and Ice Pellets",
        "71151": "Light Rain and Ice Pellets",
        "71171": "Rain and Ice Pellets",
        "71031": "Freezing Rain and Heavy Ice Pellets",
        "71131": "Mostly Clear and Heavy Ice Pellets",
        "71141": "Partly Cloudy and Heavy Ice Pellets",
        "71161": "Mostly Cloudy and Heavy Ice Pellets",
        "71011": "Heavy Ice Pellets",
        "80011": "Mostly Clear and Thunderstorm",
        "80031": "Partly Cloudy and Thunderstorm",
        "80021": "Mostly Cloudy and Thunderstorm",
        "80001": "Thunderstorm"
    }
}


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.geolocator = Nominatim(user_agent="nbot")
        self.locations = bot.db['locations']
        self.session = bot.session

        try:
            self.api_key = os.environ['CLIMACELL_API_KEY']
        except KeyError as e:
            raise Exception(f'Environment variable {e.args[0]} not set')

    @slash_command(name="weather", description='Get weather at saved or specified location')
    async def weather(self,
                      ctx,
                      location: Option(str, "Location (country, city, address, etc)", required=False)
                      ):
        if not location:
            result = await self.locations.find_one({'_id': ctx.author.id})
            if not result:
                await ctx.respond('Must provide a `location` or set a persistent location with `.setlocation`',
                                  ephemeral=True)
                return

            latitude = result['lat']
            longitude = result['long']
            address = result['addr']

        else:
            geoloc = self.geolocator.geocode(location)
            if not geoloc:
                await ctx.respond("Couldn't resolve given location", ephemeral=True)
                return

            latitude = geoloc.latitude
            longitude = geoloc.longitude
            address = geoloc.address

        url = "https://data.climacell.co/v4/timelines"
        querystring = {'apikey': os.environ['CLIMACELL_API_KEY']}
        headers = {'Content-Type': 'application/json'}
        payload = {
            'fields': ['temperature', 'temperatureApparent', 'humidity', 'windSpeed',
                       'sunsetTime', 'weatherCodeDay', 'weatherCodeNight', 'precipitationProbability',
                       'precipitationType'],
            'timesteps': ["1d"],
            'location': f'{latitude}, {longitude}'
        }

        async with self.session.post(url, json=payload, headers=headers, params=querystring) as r:
            json = await r.json()

            sunset = arrow.get(json['data']['timelines'][0]['intervals'][0]['values']['sunsetTime'])
            cur_time = arrow.utcnow()

            weather_code_key = 'weatherCodeDay' if cur_time < sunset else 'weatherCodeNight'
            weather_code = json['data']['timelines'][0]['intervals'][0]['values'][weather_code_key]
            weather_code_desc = weather_descs[weather_code_key][str(weather_code)]

            temp_c = json['data']['timelines'][0]['intervals'][0]['values']['temperature']
            temp_f = (temp_c * 9 / 5) + 32

            feel_c = json['data']['timelines'][0]['intervals'][0]['values']['temperatureApparent']
            feel_f = (feel_c * 9 / 5) + 32
            feels_like = f'Feels like {round(feel_c)}°C / {round(feel_f)}°F  — ' if feel_c != temp_c else ''

            precip_prob = json['data']['timelines'][0]['intervals'][0]['values']['precipitationProbability']
            precip_type = json['data']['timelines'][0]['intervals'][0]['values']['precipitationType']
            precip_desc = f'**{precip_descs[str(precip_type)]}**: {round(precip_prob)}% chance'
            hum = json['data']['timelines'][0]['intervals'][0]['values']['humidity']

            wind = json['data']['timelines'][0]['intervals'][0]['values']['windSpeed']
            description = f"""_{feels_like}{weather_code_desc}_
            
                **Humidity:** {round(hum)}% — **Wind**: {wind * 3.6} km/h — {precip_desc}
            """

            author_name = f'{round(temp_c)}°C / {round(temp_f)}°F'
            embed = discord.Embed(description=description, color=0x7fffd4)
            embed.set_author(name=author_name)
            # embed.set_thumbnail(url='') # TODO
            embed.set_footer(text=address)
            await ctx.respond(embed=embed)

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
