import typing

import discord
from discord.ext import commands

from src.discord.utils.nextgen import User, Guild, Member, Prefix


class IceTeaContext(commands.Context):
    def __init__(self, **kwargs):
        super(IceTeaContext, self).__init__(**kwargs)
        self.bot: "Iceteabot" = self.bot

    @property
    def prefix_data(self) -> Prefix:
        if self.guild_data is not None:
            return self.guild_data.prefixes.get(self.prefix)

    @property
    def invoked_command(self) -> commands.Command:
        return self.bot.get_command(self.invoked_with)

    @property
    async def author_data(self) -> typing.Union[Member, User]:
        return await self.get_user_data(self.author)

    @property
    def guild_data(self) -> Guild:
        if self.guild:
            return self.bot.guild_data[self.guild.id]

    def get_guild_data(self, guild: int = None) -> Guild:
        return self.bot.get_guild_data(guild)

    async def get_user_data(self, user: typing.Union[discord.Member, discord.User]) -> typing.Union[Member, User]:
        if hasattr(user, "guild"):
            guild = self.bot.get_guild_data(user.guild.id)
            if guild:
                member = await guild.get_member(user.id)
                if member:
                    return member
        else:
            return await self.bot.get_user_data(user.id)
