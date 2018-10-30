import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType


class rename:
    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(rename(bot))
