import discord
import league
import timeago
from discord.ext import commands
from discord.ext.commands import BadArgument
from discord.ext.commands import Converter
from discord.ext.commands.cooldowns import BucketType


class RegionConverter(Converter):
    async def convert(self, ctx, argument):
        region = argument.lower()
        return league.Regions[region].name


class Members:
    def __init__(self, bot):
        self.bot = bot

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        return ctx.guild

    @commands.command(aliases=["avatar"])
    @commands.cooldown(1, 30, type=BucketType.user)
    async def avatarurl(self, ctx, target: discord.Member = None):
        """Displays the authors or target's avatar url"""
        if target is None:
            await ctx.send(f"{ctx.author.avatar_url}")
        else:
            await ctx.send(f"{target.avatar_url}")

    @commands.command(aliases=['uinfo'])
    async def userinfo(self, ctx, target: discord.Member = None):
        """Display's a users information summary"""
        target = target or ctx.author
        target_data = await ctx.get_user_data(target)
        shared_servers = len([member for member in ctx.bot.get_all_members() if member == target])
        nicknames = await target_data.get_nicknames()
        embed = discord.Embed(title=f"{target.nick or target.name} Profile")
        embed.set_author(name=f"{target.name} ({target.id})", icon_url=target.avatar_url)
        embed.set_thumbnail(url=target.avatar_url)
        embed.add_field(name="Shared Servers", value=f"{shared_servers} Shared")
        embed.add_field(name="Created",
                        value=f"""{timeago.format(target.created_at)} ({target.created_at.strftime("%b %d, %Y")})""")
        embed.add_field(name="Joined",
                        value=f"""{timeago.format(target.joined_at)} ({target.joined_at.strftime("%b %d, %Y")})""")
        if len(nicknames) > 0:
            embed.add_field(name="Nicknames", value=" , ".join(str(nick) for nick in nicknames[:5]), inline=False)
        embed.add_field(name="Roles", value=" , ".join([role.name for role in target.roles[:5]]), inline=False)
        if target.activity:
            if isinstance(target.activity, discord.Spotify):
                embed.add_field(name="Currently Listening to",
                                value=f"**{target.activity.title}** by {target.activity.artist} ")
            else:
                embed.add_field(name="Currently Playing Since",
                                value=f"{target.activity.name}\n{target.activity.details}\n{target.activity.state}")
        await ctx.send(embed=embed)

    @commands.command()
    async def setleague(self, ctx, summoner_name, region: RegionConverter):
        """Sets a user league account to the database, takes in a name and a region

        possible region values:
            br
            eune
            euw
            jp
            kr
            lan
            las
            na
            oce
            tr
            ru

        """
        member_data = await ctx.author_data
        member_data.league = {'summoner': summoner_name, 'region': region}
        await ctx.message.add_reaction("\U0001f44c")
        await member_data.update()

    @setleague.error
    async def league_error(self, ctx, error):
        if isinstance(error, BadArgument):
            await ctx.send(
                f"invalid region type, use ``{ctx.prefix}help {ctx.command.qualified_name}`` for a list of valid regions")

    @commands.command()
    async def setosu(self, ctx, *, username: str):
        """Sets a user osu account to the database, takes in username"""
        member_data = await ctx.author_data
        member_data.osu = username
        await ctx.message.add_reaction("\U0001f44c")
        await member_data.update()

    @commands.command()
    async def setlocation(self, ctx, *, location: str):
        """Sets a default location to use for weather/forecast locations"""
        member_data = await ctx.author_data
        member_data.location = location
        await ctx.message.add_reaction("\U0001f44c")
        await member_data.update()

    @commands.command()
    async def setpubg(self, ctx, *, nickname: str):
        """Sets a user's pubg nickname to the database, takes in their nickname"""
        member_data = await ctx.author_data
        member_data.pubg = nickname
        await ctx.message.add_reaction("\U0001f44c")
        await member_data.update()


def setup(bot):
    bot.add_cog(Members(bot))
