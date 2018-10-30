import datetime
from io import BytesIO

import aiohttp
import discord
from discord.ext import commands
from lxml import html


class WebAPIs:
    def __init__(self, bot):
        self.bot = bot
        self.oxford_data = bot.config['oxford']

    async def getfortune(self):
        async with self.bot.aioconnection.get("http://www.fortunecookiemessage.com/") as response:
            if response.status == 200:
                tree = html.fromstring(await response.text())
                fortune = tree.xpath("//*[@id='message']/div[1]/a/text()")
                if len(fortune) == 0:
                    pass
                else:
                    return fortune[0]

    async def define_word(self, word: str, language: str = 'en'):
        """Defines a word using the Oxford Dictionary API"""
        # Gets the link and opens it as response>>de
        # data = await self.cache.get(f"ox_{word}")
        # if data is not None:
        #     return data

        async with self.bot.aioconnection.get(
                url="https://od-api.oxforddictionaries.com:443/api/v1/inflections/{}/{}".format(language, word.lower()),
                headers=dict(app_id=self.oxford_data['app_id'],
                             app_key=self.oxford_data['app_key'])) as lemmatron:
            if lemmatron.status == 200:
                lem_data = await lemmatron.json()
                if len(lem_data.get("results", [])) > 0:
                    root_word = lem_data['results'][0]['lexicalEntries'][0]['inflectionOf'][0]['id']

                    async with self.bot.aioconnection.get(
                            url="https://od-api.oxforddictionaries.com:443/api/v1/entries/{0}/{1}".format(language,
                                                                                                          root_word),
                            headers=dict(app_id=self.oxford_data['app_id'],
                                         app_key=self.oxford_data['app_key'])) as response:
                        # Checks if the response status is 200 AKA all gud
                        if response.status == 200:
                            # Returns the JSON from the link
                            data = await response.json()
                            definitions = []
                            for result in data.get("results", []):
                                if "lexicalEntries" in result:
                                    for entry in result['lexicalEntries']:
                                        for word in entry['entries']:
                                            for _ in word['senses']:
                                                if 'definitions' in _:
                                                    definitions.append(_['definitions'][0])
                            return definitions

    async def urban_dict(self, word: str):

        async with self.bot.aioconnection.get(
                "https://mashape-community-urban-dictionary.p.mashape.com/define?term={0}".format(word),
                headers={"X-Mashape-Key": "Rf5qdiAbQvmsh8qAzGmikOoVMrqkp1EEo3sjsnb7KtG3P4T4eT",
                         "Accept": "text/plain",
                         "X-Mashape-Host": "mashape-community-urban-dictionary.p.mashape.com"}) as response:
            # Checks if the response status is 200 AKA all gud
            if response.status == 200:
                # Returns the JSON from the link
                results = await response.json()

                mylist = []
                for x in range(0, 1):
                    mylist.append(results['list'][x])
                return mylist

            elif response.status == 400:
                return None
            # If status is not 200
            else:
                # Raises error for that status code
                return None

    async def xkcd_grab_specific(self, comnum: int = None):
        """Method for returning a specific comic number
        :comint: the int which represents the comic number"""
        # Checks if the response is already in redis_publisher
        # Gets the link and opens it as response
        async with self.bot.aioconnection.get("http://xkcd.com/{}/info.0.json".format(comnum)) as response:
            # Checks if the response status is 200 AKA all gud
            if response.status == 200:
                # Caches the result in redis_publisher
                # Returns the JSON from the link
                data = await response.json()
                return data

    async def xkcd_grab_newest(self):
        """Grabs the newest comic from Xkcd"""
        # Gets the link and opens it as response

        async with self.bot.aioconnection.get("http://xkcd.com/info.0.json") as response:
            # Checks if the response status is 200 AKA all gud
            if response.status == 200:
                # Returns the JSON from the link
                data = await response.json()
                return data
            # If status is not 200
            else:
                # Raises error for that status code
                raise aiohttp.ClientResponseError

    async def get_weather(self, location):
        params = {"q": location, "units": "metric", "APPID": self.bot.config['api_keys']['weather']}
        url = f"http://api.openweathermap.org/data/2.5/weather"
        async with self.bot.aioconnection.get(
                url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data

    async def get_forecast(self, location):
        params = {"q": location, "units": "metric", "APPID": self.bot.config['api_keys']['weather']}
        url = "https://api.openweathermap.org/data/2.5/forecast"
        async with self.bot.aioconnection.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data

    async def meme_generator(self, image, top, bottom):
        url = f"https://memegen.link/custom/{top}/{bottom}.jpg?alt={image}"
        async with self.bot.aioconnection.get(url) as response:
            if response.status == 200:
                data = BytesIO(await response.read())
                return data


class Websites:
    def __init__(self, bot):
        self.web_apis = WebAPIs(bot)

    def __str__(self):
        return self.__class__.__name__

    @commands.command()
    @commands.cooldown(3, 10, commands.BucketType.user)
    async def fortune(self, ctx):
        """Displays a random animal and fortune"""
        while True:
            try:
                fortune = await self.web_apis.getfortune()
                if fortune is not None:
                    return await ctx.send("```{0}```".format(fortune))
            except:
                continue

    @commands.command()
    @commands.cooldown(5, 2, commands.BucketType.user)
    async def urban(self, ctx, *, word):
        """Defines a word using the urban dictionary, provides examples"""
        results = await self.web_apis.urban_dict(word)
        if results is None:
            await ctx.send("word ``{0}`` does not exist".format(word))
        else:
            embed = discord.Embed(title="Iceteabot urban dictionary lookup", description="Urban Dictionary definer",
                                  colour=0x0023FF)
            mydef = ""
            myexp = ""
            for definition in results[:2]:
                mydef += "{0}\n".format(definition['definition'][:1023])
                myexp += "{0}\n".format(definition['example'][:1023])
            embed.add_field(name="Definition", value=mydef or "N/A")
            embed.add_field(name="Example", value=myexp or "N/A")
            await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 5)
    async def xkcd(self, ctx, comic_number: int = None):
        """Retrieves a specific XKCD comic, if left blank gets the newest one"""
        if comic_number is not None:
            comic = await self.web_apis.xkcd_grab_specific(comic_number)
        else:
            comic = await self.web_apis.xkcd_grab_newest()
        await ctx.send(comic['img'])

    @commands.command()
    @commands.cooldown(5, 15, type=commands.BucketType.user)
    async def define(self, ctx, *, word):
        """Defines a word from the Oxford dictionary"""
        response = await self.web_apis.define_word(word)
        if response is None or len(response) == 0:
            await ctx.send("Word does not exist in my dictionary")
        else:
            embed = discord.Embed(title="Iceteabot Definer", description=f"Definition for {word}")
            counter = 1
            for entry in response[:4]:
                embed.add_field(name=f"Definiton {counter}", value=entry, inline=False)
                counter += 1
            await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def weather(self, ctx, *, location=None):
        """Displays current weather information based on a location given"""
        author_data = await ctx.author_data
        if location is None:
            location = author_data.location
        if location is None:
            raise commands.BadArgument(message=ctx.message.content)
        weather_data = await self.web_apis.get_weather(location)
        if weather_data is not None:
            try:
                fahrenheit = int(int(weather_data['main']['temp']) * (9 / 5) + 32)
                mph = int(weather_data['wind']['speed']) * 2.237
                embed = discord.Embed(
                    title=f"Weather for {weather_data['name']},{weather_data['sys']['country']}",
                    description=f"*{weather_data['weather'][0]['description']}*",

                )
                embed.set_thumbnail(url=f"http://openweathermap.org/img/w/{weather_data['weather'][0]['icon']}.png")
                embed.add_field(name="Temperature", value=f"{int(weather_data['main']['temp'])}°C | {fahrenheit} °F")
                embed.add_field(name='Humidity', value=f"{weather_data['main']['humidity']}%")
                embed.add_field(name="Wind", value=f"{int(mph)} mph")
                embed.set_footer(text="Data provided by: openweathermap")
            except:
                return await ctx.send("Unable to find weather data")

            return await ctx.send(embed=embed)

    @weather.error
    async def weather_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("You need to specify a location")

    @commands.command()
    @commands.cooldown(5, 20, commands.BucketType.user)
    async def forecast(self, ctx, *, location=None):
        """Display's a 5 day forecast"""
        author_data = await ctx.author_data

        if location is None:
            location = author_data.location
        if location is None:
            raise commands.BadArgument(message=location)
        days = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
        checked_days = []
        data = await self.web_apis.get_forecast(location)
        if data is not None:
            try:
                embed = discord.Embed(title=f"5 Day Forecast for {data['city']['name']}")
                for day in data['list']:
                    date = datetime.datetime.strptime(day['dt_txt'], "%Y-%m-%d %H:%M:%S")
                    if date.weekday() in checked_days:
                        continue
                    checked_days.append(date.weekday())
                    weather = day['main']
                    fahrenheit = int(int(weather['temp']) * (9 / 5) + 32)
                    mph = round(int(day['wind']['speed']) * 2.237, 2)
                    embed.add_field(name=f"{days[date.weekday()]}",
                                    value=f"\U0001f321 : {weather['temp']}C/{fahrenheit}F\n"
                                          f"\U0001f4a8 : {round(day['wind']['speed'], 2)}Kmh/{mph}Mph\n"
                                          f"\U0001f525 : {weather['humidity']}%",
                                    inline=False)
            except:
                return await ctx.send("Unable to get forecast data")

            await ctx.send(embed=embed)

    @forecast.error
    async def forecast_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("You need to specify a location")


def setup(bot):
    bot.add_cog(Websites(bot))
