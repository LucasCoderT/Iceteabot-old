import asyncio
import datetime
import math
import traceback

import discord
import osuapi
import timeago
from discord.ext import commands
from discord.ext.commands import Converter, MemberConverter
from discord.ext.commands.cooldowns import BucketType
from osuapi import OsuMode

from src.discord.utils.errors import MissingConnection, NoAccountFound
from src.discord.utils.paginator import OsuHistoryPaginator, OsuBestPaginator


class OsuConverter(Converter):

    async def convert(self, ctx, argument):
        if argument is None:
            argument = ctx.author
        if isinstance(argument, (discord.Member, discord.User)):
            member_data = ctx.get_user_data(argument)
            if member_data.osu:
                return member_data.osu
            else:
                raise MissingConnection("osu", argument)
        else:
            return argument


class OsuModeConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            modes = {"osu": 0, "takio": 1, "ctb": 2, "mania": 3}
            return OsuMode[modes[argument.lower()]]
        except:
            raise commands.UserInputError(f"{argument} is not a valid osu game mode")


class Osu:
    def __init__(self, bot):
        self.bot = bot
        self.session = osuapi.AHConnector()
        self.osu = osuapi.OsuApi(bot.config['api_keys']['osu'], connector=self.session)

    def __str__(self):
        return self.__class__.__name__

    async def __error(self, ctx, error):
        if isinstance(error, (NoAccountFound, commands.BadArgument, MissingConnection)):
            await ctx.send(error)
        else:
            await ctx.send(f"""```\n{traceback.format_tb(error.original.__traceback__)}\n```""", delete_after=30)

    def __unload(self):
        asyncio.ensure_future(self.session.sess.close())

    async def get_user_data(self, ctx, username, mode):
        if isinstance(mode, OsuMode):
            game_mode = mode
        else:
            game_mode = await OsuModeConverter().convert(ctx, mode)

        if username is not None:
            user_data = await self.osu.get_user(username, mode=game_mode)
            if len(user_data) == 0:
                user_target = await MemberConverter().convert(ctx, username)
                user_data = await OsuConverter().convert(ctx, user_target)
                user_data = await self.osu.get_user(user_data, mode=game_mode)
                if len(user_data) > 0:
                    return user_data[0], game_mode

        else:
            user_target = await OsuConverter().convert(ctx, username)
            user_data = await self.osu.get_user(user_target, mode=game_mode)
        if len(user_data) > 0:
            return user_data[0], game_mode

    @commands.command(aliases=['oprofile'])
    @commands.cooldown(30, 1, BucketType.user)
    async def osuprofile(self, ctx, username=None, mode=OsuMode.osu):
        """Returns a summary of the users osu profile
        defaults to standard mode
         options: std,taiko,ctb,mania"""
        user_data, game_mode = await self.get_user_data(ctx, username, mode)
        embed = discord.Embed()
        embed.title = "{0} {1} profile".format(user_data.username, game_mode)
        embed.url = "https://new.ppy.sh/u/{0}".format(user_data.user_id)
        embed.set_thumbnail(url='https://new.ppy.sh/images/layout/osu-logo.png')
        embed.add_field(name='level', value=f"{math.trunc(float(user_data.level))}")
        embed.add_field(name='accuracy', value=f"{math.trunc(float(user_data.accuracy))}%")
        embed.add_field(name='Country', value=f":flag_{user_data.country.lower()}:")
        embed.add_field(name='Global Rank', value="{:,}".format(int(user_data.pp_rank)))
        embed.add_field(name=f'Country rank', value="{:,}".format(int(user_data.pp_country_rank)))
        embed.add_field(name='Play Count', value="{:,}".format(int(user_data.playcount)))
        if len(user_data.events) > 0:
            recent_events = []
            for event in user_data.events:
                beat_map_data = await self.osu.get_beatmaps(mode=game_mode, beatmap_id=event.beatmap_id,
                                                            username=user_data.username)
                if beat_map_data is not None and len(beat_map_data) > 0:
                    recent_events.append(f"**Beatmap** : {beat_map_data.title}\n"
                                         f"**Time** : {timeago.format(event.date,now=datetime.datetime.now(tz=datetime.timezone.utc))}\n"
                                         f"**EpicFactor** : {event.epicfactor}\n")
            if len(recent_events) > 0:
                embed.add_field(name="Recent Events", value="".join(recent_events))
        await ctx.send(embed=embed)

    @commands.command(aliases=['osutop', 'otop', 'obest'])
    @commands.cooldown(30, 1, BucketType.user)
    async def osubest(self, ctx, username=None, mode=OsuMode.osu):
        """Displays a targets top 5 best beatmap plays for a specified mode"""
        user_data, game_mode = await self.get_user_data(ctx, username, mode)
        best_plays = await self.osu.get_user_best(username=user_data.username, mode=game_mode)
        if best_plays is not None and best_plays:
            paginator = OsuBestPaginator(ctx, best_plays, user_data=user_data, game_mode=game_mode, osu_client=self.osu)
            await paginator.paginate()

    @commands.command(aliases=['osuhistory', 'ohistory'])
    @commands.cooldown(30, 1, BucketType.user)
    async def osurecent(self, ctx, username=None, mode=OsuMode.osu):
        """Displays 5 most recent plays for a target in a specified mode"""
        user_data, game_mode = await self.get_user_data(ctx, username, mode)
        recent_plays = await self.osu.get_user_recent(username=user_data.username, mode=game_mode)
        if recent_plays is not None and recent_plays:
            paginator = OsuHistoryPaginator(ctx, recent_plays, user_data=user_data, game_mode=game_mode)
            await paginator.paginate()
        else:
            await ctx.send(f"{user_data.username} has not played any {game_mode} games in the past 24 hours.")


def setup(bot):
    bot.add_cog(Osu(bot))
