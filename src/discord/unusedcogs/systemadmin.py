import re

from discord.ext import commands

from src.discord.utils.permissions import owner


class SystemAdministrator:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, hidden=True)
    @commands.check(owner)
    async def startconnection(self, ctx, *, sshstr):
        sshmatch = re.search(r'(.+?(?=@))(\@(.*))', sshstr)
        await ctx.send(sshmatch)


def setup(bot):
    bot.add_cog(SystemAdministrator(bot))
