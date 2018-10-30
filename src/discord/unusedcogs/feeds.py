import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType


class Feeds:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['f'])
    async def feeds(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("You need to use a sub command")

    @feeds.command()
    async def create(self, ctx):
        pass


def setup(bot):
    bot.add_cog(Feeds(bot))
