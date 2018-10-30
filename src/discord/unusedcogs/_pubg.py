import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType


class PubGConverter(commands.Converter):
    async def convert(self, ctx, argument):
        pass


class PubG:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def pubgprofile(self, ctx, username: PubGConverter):
        pass


def setup(bot):
    bot.add_cog(PubG(bot))
