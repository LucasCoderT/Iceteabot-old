import re

import discord
from discord.ext import commands
from discord.ext.commands import Converter, errors

from src.discord.utils import errors as myerrors
from src.discord.utils import time


class GuildCommandConverter(Converter):
    async def convert(self, ctx, argument):
        if ctx.command.parent is not None:
            g_command = await ctx.bot.factory.Command.get(argument, connection=ctx.bot.rethinkdb, bot=ctx.bot)
            if g_command is not None:
                return g_command
            else:
                raise myerrors.NotRootCommand(argument)
        else:
            raise errors.BadArgument(
                message=f"{ctx.command.invoked_with} cannot be blocked, only parent commands can be blocked.")


class GuildConverter(Converter):
    async def convert(self, ctx, argument):
        guild = discord.utils.get(ctx.bot.guilds, name=argument)
        if guild is None:
            guild = discord.utils.get(ctx.bot.guilds, id=int(argument))
        if guild is None:
            raise errors.BadArgument(message="I am not in any guild with this ID")
        else:
            return guild


async def is_guild_admin(ctx):
    return any([ctx.author == ctx.bot.owner,
                all([ctx.author.guild_permissions.administrator, ctx.author.guild_permissions.manage_guild])])


class Server:
    def __init__(self, bot):
        self.bot = bot

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        return getattr(ctx, "guild") and ctx.guild is not None

    async def __error(self, ctx, error):
        if hasattr(error, "original"):
            pass
        elif isinstance(error, myerrors.NotRootCommand):
            return await ctx.send(
                f"You can only disable parent commands, I am unable to handle blocking child commands")

    @staticmethod
    def clean_tag_content(content):
        return content.replace('@everyone', '@\u200beveryone').replace('@here', '@\u200bhere')

    @commands.command(name="guildinfo", aliases=["ginfo"])
    async def guild_info(self, ctx, target_server: GuildConverter = None):
        """Tells you information about the server or about a specific server, assuming the bot is in that server"""
        target_server = ctx.guild if target_server is None else target_server
        total_members = len(target_server.members)
        total_online = sum(
            1 for m in target_server.members if m.status != discord.Status.offline and m.bot is not True)
        text = len(target_server.text_channels)
        voice = len(target_server.voice_channels)
        region = target_server.region
        created_at = target_server.created_at.strftime("%b %d, %Y")
        owner = target_server.owner
        roles = len(target_server.roles)
        emojis = len(target_server.emojis)
        verificationlevel = target_server.verification_level
        members = "{0} total\n{1} online".format(total_members, total_online)

        embed = discord.Embed()
        embed.set_thumbnail(url=target_server.icon_url)
        embed.title = "{0} Server information".format(target_server.name)
        embed.colour = 0x0023FF
        embed.add_field(name='Owner', value=owner.mention)
        embed.add_field(name='Members', value=members)
        embed.add_field(name='Channels', value="{0} total\n{1} text\n{2} Voice".format(text + voice, text, voice))
        embed.add_field(name='Custom Emotes', value=str(emojis))
        embed.add_field(name='Roles', value=str(roles))
        embed.add_field(name='Verification Level', value=verificationlevel)
        embed.add_field(name='Region', value=region)
        embed.add_field(name='Created', value=created_at)
        await ctx.send(embed=embed)

    @commands.command()
    async def newemojis(self, ctx, *, count=5):
        """Tells you the newest emojis of the server.

        The count parameter can only be up to 50.
        """
        count = max(min(count, 50), 5)
        emojis = sorted(ctx.guild.emojis, key=lambda m: m.created_at, reverse=True)[:count]

        e = discord.Embed(title='New Emojis', colour=discord.Colour.green())

        for emoji in emojis:
            body = f'created {time.human_timedelta(emoji.created_at)}'
            e.add_field(name=f'{emoji} (Name: {emoji.name}) (ID: {emoji.id})', value=body, inline=False)

        await ctx.send(embed=e)

    @commands.group(name="prefix", invoke_without_command=True)
    async def _prefix(self, ctx):
        """Prefix managing command, use ``help prefix`` for more information
        Displays a list of this server's prefixes if left blank"""
        guild_data = ctx.guild_data.prefixes
        if len(guild_data) != 0:
            embed = discord.Embed(title=f"Prefixes for {ctx.guild}")
            embed.add_field(name="\u200b", value="\n".join(f"{prefix}" for prefix in guild_data))
            await ctx.send(embed=embed)
        else:
            await ctx.send("This server has no prefixes set.")

    @_prefix.command(name="set", aliases=['add', "create"])
    @commands.check(is_guild_admin)
    async def set(self, ctx, *, prefix: str):
        """Sets a server's prefix. Only server administrators can set prefixes"""
        if " " in prefix:
            return await ctx.send("You cannot set prefixes with a space")
        elif re.search(r'<@!?([0-9]+)>$', prefix):
            return await ctx.send("You cannot add a mention as a prefix")
        current_prefixes = ctx.guild_data.prefixes
        if prefix in current_prefixes:
            return await ctx.send("This prefix already exists")
        new_prefix = await ctx.guild_data.create_prefix(prefix, ctx.author.id)
        if new_prefix is not None:
            await ctx.send(
                f"Successfully added {prefix}, this guild now has {len(current_prefixes)} prefixes")

    @_prefix.command(name="delete", aliases=['del'])
    @commands.check(is_guild_admin)
    async def delete(self, ctx, *, prefix: str):
        """Deletes a given prefix if it exists. Only server administrators can delete prefixes"""
        if re.search(r'<@!?([0-9]+)>$', prefix):
            await ctx.send("You cannot remove the mention prefix")
            return
        target_prefix = await ctx.guild_data.delete_prefix(prefix)
        if target_prefix is None:
            return await ctx.send("No prefix found")
        else:
            await ctx.send(
                f"Successfully deleted this prefix. "
                f"This server now has {len(ctx.guild_data.prefixes)} prefixes")

    @_prefix.command(name="stats")
    async def prefixstats(self, ctx):
        """Displays a leaderboard of most used prefixes for this server"""
        prefixes = list(sorted(ctx.guild_data.prefixes.values(), key=lambda prefix: prefix.uses))
        message = []
        if len(prefixes) >= 1:
            for prefix in prefixes:
                message.append(f"{prefix}: {prefix.uses}\n")
            await ctx.send(f"```py\n{''.join(message)}```")
        else:
            await ctx.send("This server has no prefixes set")

    @commands.command(aliases=['newmembers'])
    @commands.guild_only()
    async def newusers(self, ctx, *, count=5):
        """Tells you the newest members of the server.

        This is useful to check if any suspicious members have
        joined.

        The count parameter can only be up to 25.
        """
        count = max(min(count, 25), 5)
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:count]

        e = discord.Embed(title='New Members', colour=discord.Colour.green())

        for member in members:
            body = f'joined {time.human_timedelta(member.joined_at)}, ' \
                   f'created {time.human_timedelta(member.created_at)}'
            e.add_field(name=f'{member} (ID: {member.id})', value=body, inline=False)

        await ctx.send(embed=e)

    @commands.command(name="joinch")
    @commands.check(is_guild_admin)
    @commands.bot_has_permissions(send_messages=True, read_messages=True)
    async def set_join_channel(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel that the bot will send a message to when a user joins the server."""
        if channel in ctx.guild.text_channels:
            permissions = channel.permissions_for(ctx.me)
            if permissions.send_messages:
                ctx.guild_data.welcome_channel = channel.id
                await ctx.guild_data.update()
                await ctx.send(f"Successfully set join channel, I will now welcome members in the channel {channel}")

    @commands.command(name="leavech")
    @commands.check(is_guild_admin)
    @commands.bot_has_permissions(send_messages=True, read_messages=True)
    async def set_leave_channel(self, ctx, channel: discord.TextChannel = None):
        """Toggles if you want the bot to send a message when a user leaves the server"""
        if channel in ctx.guild.text_channels:
            permissions = channel.permissions_for(ctx.me)
            if permissions.send_messages:
                ctx.guild_data.welcome_channel = channel.id
                await ctx.guild_data.update()
                await ctx.send(
                    f"Successfully set leaving channel, I will now notify when members "
                    f"leave members in the channel {channel}")

    @commands.command(name="gtrack")
    @commands.check(is_guild_admin)
    async def set_tracking(self, ctx):
        """This tells the bot to track user nickname's. The bot will keep a record of all nicknames a user has had."""
        ctx.guild_data.tracking = not ctx.guild_data.tracking
        await ctx.send(f"Guild tracking has now been set to **{ctx.guild_data.tracking}**")
        await ctx.guild_data.update()

    @commands.command(name="joinmsg")
    @commands.check(is_guild_admin)
    async def set_join_message(self, ctx, *, message):
        """Sets the server's join message, must be enabled first by setting a channel see ``help joinch``"""
        message = self.clean_tag_content(message)
        ctx.guild_data.welcome_message = message
        await ctx.guild_data.update()
        await ctx.send("Set Join Message")

    @commands.command(name="leavemsg")
    @commands.check(is_guild_admin)
    async def set_leave_message(self, ctx, *, message):
        """Sets the server's leave message, must be enabled first see ``help leavech``"""
        message = self.clean_tag_content(message)
        ctx.guild_data.leaving_message = message
        await ctx.guild_data.update()
        await ctx.send("Set Leave Message")

    @commands.command(name="disablecmd")
    @commands.check(is_guild_admin)
    async def block_command(self, ctx, target: discord.TextChannel = None, *, reason=None):
        """Prevents the bot from responding to any commands in this channel"""
        target_channel = target or ctx.channel
        if target_channel in ctx.guild.channels:
            response = await ctx.guild_data.block_channel(target_channel.id, ctx.author.id, reason)
            if response:
                await ctx.send("I will no longer respond to commands in this channel")

    @commands.command(name="enablecmd")
    @commands.check(is_guild_admin)
    async def unblock_command(self, ctx, target: discord.TextChannel = None):
        """Unblocks a channel, meaning the bot can respond to commands"""
        target_channel = target or ctx.channel
        if target_channel in ctx.guild.channels:
            response = await ctx.guild_data.unblock_channel(target_channel.id)
            if response:
                await ctx.send("I will now respond to commands in this channel")

    @commands.command(name="newuserrole")
    @commands.check(is_guild_admin)
    @commands.bot_has_permissions(manage_roles=True)
    async def set_new_role(self, ctx, target_role: discord.Role = None, when: int = 0):
        """
        Automatically assigns a role to a user, upon joining the server.
        Can only be used by server managers
        it has an optimal param to allow the bot to give the role after x seconds, If not set, will give the user the
        role right away. If you wish to disable this function after it's been enabled simply run this command without
        giving it a role.
        """
        if target_role < ctx.me.top_role and not target_role.is_default():
            ctx.guild_data.role = target_role.id
            ctx.guild_data.delay = when
            await ctx.guild_data.update()
            await ctx.send(f"I will now give {target_role} to new members")

    # @commands.command(name="chtoggle")
    # async def channel_command_toggle(self, ctx, *, command_name: GuildCommandConverter):
    #     """Disables a command for a specific channel"""
    #     if str(ctx.channel.id) in command_name.channels_blocked:
    #         command_name.channels_blocked.remove(str(ctx.channel.id))
    #         await ctx.send(f"**{command_name}** has been unblocked in this channel")
    #     else:
    #         command_name.channels_blocked.append(str(ctx.channel.id))
    #         await ctx.send(f"**{command_name}** has been blocked in this channel")
    #     await command_name.save()
    #

    # @commands.command()
    # @commands.check(is_guild_admin)
    # async def subcreate(self, ctx, url: str, channel: discord.TextChannel = None):
    #     """Adds a rssfeed to monitor updates, posts in channel if update occurs.
    #     if channel is left blank will use the channel the command is posted in"""
    #     try:
    #         feed_data = feedparser.parse(url)
    #         newest_entry = feed_data['entries'][0]
    #         try:
    #             thumbnail = newest_entry['media_thumbnail'][0]['url']
    #         except:
    #             thumbnail = None
    #         embed = discord.Embed(title=f"New post {newest_entry['title']}")
    #         embed.add_field(name='New Content', value=newest_entry['description'][:200])
    #         embed.add_field(name="Url", value=newest_entry['link'])
    #         embed.set_thumbnail(url=thumbnail)
    #         embed.timestamp = datetime.datetime.fromtimestamp(mktime(newest_entry['published_parsed']))
    #     except Exception as e:
    #         await ctx.bot.owner.send(e, delete_after=30)
    #         return await ctx.send("Unable to parse this url")
    #     target_channel = ctx.channel if channel is None else channel
    #     rss_feed = await self.bot.icethinkdb.get_subscription(url)
    #     rss_feed.new_sub(target_channel)
    #     await rss_feed.save()
    #     await ctx.send(f"I will now notify {target_channel.mention} when this page gets updated")
    #
    # @commands.command(aliases=['unsub'])
    # @commands.check(is_guild_admin)
    # async def subremove(self, ctx, url: str, channel: discord.TextChannel = None):
    #     """Will delete the feed from the provided channel or from the channel the command was used in"""
    #     target_channel = channel if channel is not None else ctx.channel
    #     sub_data = await self.bot.icethinkdb.get_subscription(url)
    #     sub_data.remove_sub(target_channel)
    #     await sub_data.save()
    #     await ctx.send("This channel is no longer subscribed to this feed")
    #
    # @commands.command(name="sublist", aliases=['activefeeds', 'feeds'])
    # async def active_subscriptions(self, ctx, channel: discord.TextChannel = None):
    #     """Lists all currently active subscriptions in the given channel.
    #     if channel is left blank will use the channel the command was used in."""
    #     target_channel = channel if channel is not None else ctx.channel
    #     channel_subs = self.get_subscriptions_by_channel(target_channel)
    #     if not channel_subs:
    #         return await ctx.send(f"{target_channel.mention} channel is not subscribed to any feeds")
    #     embed = discord.Embed(title="Active Subscriptions")
    #     embed.add_field(name="Subs",
    #                     value="\n".join(sub.id for sub in self.get_subscriptions_by_channel(target_channel)))
    #     await ctx.send(embed=embed)
    #
    # def get_subscriptions_by_channel(self, channel: discord.TextChannel):
    #     return [feed for feed in self.bot.subscriptions.values() if str(channel.id) in feed.channels]


def setup(bot):
    bot.add_cog(Server(bot))
