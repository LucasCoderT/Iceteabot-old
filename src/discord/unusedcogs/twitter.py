import configparser
import os

import discord
import wolframalpha
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType



class Twitter:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, nopm=False, hidden=True)
    @commands.cooldown(30, 1, BucketType.user)
    async def icetweet(self, ctx):


def setup(bot):
    bot.add_cog(Twitter(bot))
