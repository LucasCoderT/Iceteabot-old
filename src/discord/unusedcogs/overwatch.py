from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType


class OverWatch:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    @commands.cooldown(30, 1, BucketType.user)
    async def owprofile(self, ctx, target_user: str = None, region: str = 'us', platform: str = 'pc'):
        """Displays the USER OverWatch profile"""
        target = None
        pass


def setup(bot):
    bot.add_cog(OverWatch(bot))
