import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
import rethinkdb as r


class Incident:
    def __init__(self, event_type, target_user, responsible_moderator, reason=None, case_number=None, bot=None):
        self.event_type = event_type
        self.target_user = str(target_user)
        self.responsible_moderator = str(responsible_moderator)
        self.reason = reason
        self.case_number = case_number
        self.bot = bot

    async def save(self):
        pass


class ModLog:
    def __init__(self, bot):
        self.bot = bot

    async def on_member_ban(self, guild, user):
        pass

    async def on_member_unban(self, guild, user):
        pass

    async def on_member_remove(self, member):
        pass

    async def on_member_join(self, member):
        pass


def setup(bot):
    bot.add_cog(ModLog(bot))
