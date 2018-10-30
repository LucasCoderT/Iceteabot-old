import datetime

import discord
import timeago
from discord.ext import commands


class Bus:
    def __init__(self, **kwargs):
        self.arrival_time = datetime.datetime.strptime(kwargs['arrival_time'], "%H:%M:%S")
        self.departure_time = datetime.datetime.strptime(kwargs['departure_time'], "%H:%M:%S")
        self.drop_off_type = kwargs['drop_off_type']
        self.pickup_type = kwargs['pickup_type']
        self.stop_id = kwargs['stop_id']
        self.stop_sequence = kwargs['stop_sequence']
        self.trip_id = kwargs['trip_id']
        self.route_id = kwargs['route_id']

    def __eq__(self, other):
        return self.arrival_time == other.arrival_time


class ETS:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://data.edmonton.ca/resource/"

    def __str__(self):
        return self.__class__.__name__

    async def get_stop_times(self, stop_id: int):
        schedule = []
        now = datetime.datetime.now()
        time_formatted = now.strftime("%H:%M:%S")
        future_now = now + datetime.timedelta(hours=1)
        future_now_formatted = future_now.strftime("%H:%M:%S")
        params = {
            "stop_id": stop_id,
            "$where": f"arrival_time between '{time_formatted}' and '{future_now_formatted}'"
        }
        query = f"?stop_id={params['stop_id']}&$where={params['$where']}&$order=arrival_time ASC"
        async with self.bot.aioconnection.get(f"{self.base_url}brqx-qet8.json{query}") as response:
            if response.status == 200:
                data = await response.json()
                for route in data:
                    async with self.bot.aioconnection.get(
                            f"{self.base_url}qguy-a9de.json?trip_id={route['trip_id']}") as response_two:
                        if response_two.status == 200:
                            data_two = await response_two.json()
                            bus = Bus(**route, route_id=data_two[0]['route_id'])
                            if bus in schedule:
                                continue
                            schedule.append(bus)
                return schedule

    @commands.command(hidden=True)
    async def ets(self, ctx, route_id: int):
        """Edmonton Only, gets bus routes via bus-stop number.
        """
        async with ctx.typing():
            data = await self.get_stop_times(route_id)
            embed = discord.Embed(title=f"ETS Bus schedule for stop {route_id}")
            for bus in data:
                full_date = datetime.datetime.now().replace(hour=bus.arrival_time.hour, minute=bus.arrival_time.minute,
                                                            second=bus.arrival_time.second)
                embed.add_field(name=f"Bus: {bus.route_id}",
                                value=f"{bus.arrival_time.strftime('%I:%M %p')} **({timeago.format(full_date)})**",
                                inline=False)
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(ETS(bot))
