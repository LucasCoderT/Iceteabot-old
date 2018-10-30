import discord
from discord.ext import commands

from src.discord.utils.errors import *


async def check_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


def has_permissions(*, check=all, **perms):
    async def pred(ctx):
        return await check_permissions(ctx, perms, check=check)

    return commands.check(pred)


async def check_guild_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.server is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


def has_guild_permissions(*, check=all, **perms):
    async def pred(ctx):
        return await check_guild_permissions(ctx, perms, check=check)

    return commands.check(pred)


# These do not take channel overrides into account

def is_mod():
    async def pred(ctx):
        return await check_guild_permissions(ctx, {'manage_guild': True})

    return commands.check(pred)


def is_admin():
    async def pred(ctx):
        return await check_guild_permissions(ctx, {'administrator': True})

    return commands.check(pred)


def mod_or_permissions(**perms):
    perms['manage_guild'] = True

    async def predicate(ctx):
        return await check_guild_permissions(ctx, perms, check=any)

    return commands.check(predicate)


def admin_or_permissions(**perms):
    perms['administrator'] = True

    async def predicate(ctx):
        return await check_guild_permissions(ctx, perms, check=any)

    return commands.check(predicate)


def is_in_guilds(*guild_ids):
    def predicate(ctx):
        guild = ctx.server
        if guild is None:
            return False
        return guild.id in guild_ids

    return commands.check(predicate)


async def guildowner(ctx):
    if ctx.author == ctx.server.owner:
        return True
    else:
        raise NotGuildOwner


async def privatemessage(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        return True
    else:
        raise NotDirectMessage


async def bot_moderator(ctx):
    user_data = await ctx.user_data()
    return user_data.permissions['moderator'] or await ctx.bot.is_owner(ctx.author)


async def guild_administrator(ctx):
    permissions = ctx.author.guild_permissions
    return permissions.administrator


async def bot_administrator(ctx):
    user_data = await ctx.user_data()
    return user_data.permissions['administrator'] or await ctx.bot.is_owner(ctx.author)


if __name__ == '__main__':
    pass
