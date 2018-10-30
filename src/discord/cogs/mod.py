import argparse
import enum
import logging
import re
import shlex
from collections import Counter, defaultdict

import discord
from discord.ext import commands

from src.discord.utils import permissions as checks
from src.discord.utils import time

log = logging.getLogger(__name__)


## Misc utilities

class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


class RaidMode(enum.Enum):
    off = 0
    on = 1
    strict = 2

    def __str__(self):
        return self.name


## Tables


## Configuration

class ModConfig:
    __slots__ = ('raid_mode', 'broadcast_channel', 'mention_count', 'safe_mention_channel_ids')

    @classmethod
    async def from_record(cls, record, bot):
        self = cls()

        # the basic configuration
        guild = bot.get_guild(record['id'])
        self.raid_mode = record['raid_mode']
        self.broadcast_channel = guild.get_channel(record['broadcast_channel'])
        self.mention_count = record['mention_count']
        self.safe_mention_channel_ids = set(record['safe_mention_channel_ids'] or [])
        return self


## Converters

class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                return int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None
        else:
            can_execute = ctx.author.id == ctx.bot.owner_id or \
                          ctx.author == ctx.guild.owner or \
                          ctx.author.top_role > m.top_role

            if not can_execute:
                raise commands.BadArgument('You cannot do this action on this user due to role hierarchy.')
            return m.id


class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        ban_list = await ctx.guild.bans()
        try:
            member_id = int(argument, base=10)
            entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
        except ValueError:
            entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)

        if entity is None:
            raise commands.BadArgument("Not a valid previously-banned member.")
        return entity


class ActionReason(commands.Converter):
    async def convert(self, ctx, argument):
        ret = f'{ctx.author} (ID: {ctx.author.id}): {argument}'

        if len(ret) > 512:
            reason_max = 512 - len(ret) - len(argument)
            raise commands.BadArgument(f'reason is too long ({len(argument)}/{reason_max})')
        return ret


## The actual cog

class Mod:
    """Moderation related commands."""

    def __init__(self, bot):
        self.bot = bot

        # _guild_id: set(user_id)
        self._recently_kicked = defaultdict(set)

    def __repr__(self):
        return '<cogs.Mod>'

    def __str__(self):
        return self.__class__.__name__

    async def __error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.NotFound):
                await ctx.send(f'This entity does not exist: {original.text}')
            elif isinstance(original, discord.HTTPException):
                await ctx.send('Somehow, an unexpected error occurred. Try again later?')

    async def _basic_cleanup_strategy(self, ctx, search):
        count = 0
        async for msg in ctx.history(limit=search, before=ctx.message):
            if msg.author == ctx.me:
                await msg.delete()
                count += 1
        return {'Bot': count}

    async def _complex_cleanup_strategy(self, ctx, search):
        guild_data = await ctx.guild_data()
        prefixes = [key for key in guild_data.prefixes.keys()]

        def check(m):
            return m.author == ctx.me or any([m.content.startswith(prefix) for prefix in prefixes])

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    @commands.command()
    @checks.has_permissions(manage_messages=True)
    async def cleanup(self, ctx, search=100):
        """Cleans up the bot's messages from the channel.

        If a search number is specified, it searches that many messages to delete.
        If the bot has Manage Messages permissions then it will try to delete
        messages that look like they invoked the bot as well.

        After the cleanup is completed, the bot will send you a message with
        which people got their messages deleted and their count. This is useful
        to see which users are spammers.

        You must have Manage Messages permission to use this.
        """

        strategy = self._basic_cleanup_strategy
        if ctx.me.permissions_in(ctx.channel).manage_messages:
            strategy = self._complex_cleanup_strategy

        spammers = await strategy(ctx, search)
        deleted = sum(spammers.values())
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'- **{author}**: {count}' for author, count in spammers)

        await ctx.send('\n'.join(messages), delete_after=10)

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: ActionReason = None):
        """Kicks a member from the server.

        In order for this to work, the bot must have Kick Member permissions.

        To use this command you must have Kick Members permission.
        """

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        await member.kick(reason=reason)
        await ctx.send('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def ban(self, ctx, member: MemberID, *, reason: ActionReason = None):
        """Bans a member from the server.

        You can also ban from ID to ban regardless whether they're
        in the server or not.

        In order for this to work, the bot must have Ban Member permissions.

        To use this command you must have Ban Members permission.
        """

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        await ctx.guild.ban(discord.Object(id=member), reason=reason)
        await ctx.send('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def massban(self, ctx, reason: ActionReason, *members: MemberID):
        """Mass bans multiple members from the server.

        You can also ban from ID to ban regardless whether they're
        in the server or not.

        Note that unlike the ban command, the reason comes first
        and is not optional.

        In order for this to work, the bot must have Ban Member permissions.

        To use this command you must have Ban Members permission.
        """

        for member_id in members:
            await ctx.guild.ban(discord.Object(id=member_id), reason=reason)

        await ctx.send('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(kick_members=True)
    async def softban(self, ctx, member: MemberID, *, reason: ActionReason = None):
        """Soft bans a member from the server.

        A softban is basically banning the member from the server but
        then unbanning the member as well. This allows you to essentially
        kick the member while removing their messages.

        In order for this to work, the bot must have Ban Member permissions.

        To use this command you must have Kick Members permissions.
        """

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        obj = discord.Object(id=member)
        await ctx.guild.ban(obj, reason=reason)
        await ctx.guild.unban(obj, reason=reason)
        await ctx.send('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def unban(self, ctx, member: BannedMember, *, reason: ActionReason = None):
        """Unbans a member from the server.

        You can pass either the ID of the banned member or the Name#Discrim
        combination of the member. Typically the ID is easiest to use.

        In order for this to work, the bot must have Ban Member permissions.

        To use this command you must have Ban Members permissions.
        """

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        await ctx.guild.unban(member.user, reason=reason)
        if member.reason:
            await ctx.send(f'Unbanned {member.user} (ID: {member.user.id}), previously banned for {member.reason}.')
        else:
            await ctx.send(f'Unbanned {member.user} (ID: {member.user.id}).')

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def tempban(self, ctx, duration: time.FutureTime, member: MemberID, *, reason: ActionReason = None):
        """Temporarily bans a member for the specified duration.

        The duration can be a a short time form, e.g. 30d or a more human
        duration such as "until thursday at 3PM" or a more concrete time
        such as "2017-12-31".

        Note that times are in UTC.

        You can also ban from ID to ban regardless whether they're
        in the server or not.

        In order for this to work, the bot must have Ban Member permissions.

        To use this command you must have Ban Members permission.
        """

        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        reminder = self.bot.get_cog('Reminder')
        if reminder is None:
            return await ctx.send('Sorry, this functionality is currently unavailable. Try again later?')

        await ctx.guild.ban(discord.Object(id=member), reason=reason)
        timer = await reminder.create_timer(ctx, duration, "tempban_timer_complete")
        await ctx.send(f'Banned ID {member} for {time.human_timedelta(duration.dt)}.')

    async def on_tempban_timer_complete(self, timer):
        guild_id, mod_id, member_id = timer.args

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            # RIP
            return

        moderator = guild.get_member(mod_id)
        if moderator is None:
            try:
                moderator = await self.bot.get_user_info(mod_id)
            except:
                # request failed somehow
                moderator = f'Mod ID {mod_id}'
            else:
                moderator = f'{moderator} (ID: {mod_id})'
        else:
            moderator = f'{moderator} (ID: {mod_id})'

        reason = f'Automatic unban from timer made on {timer.created_at} by {moderator}.'
        await guild.unban(discord.Object(id=member_id), reason=reason)

    @commands.group(aliases=['purge'])
    @commands.guild_only()
    @checks.has_permissions(manage_messages=True)
    async def remove(self, ctx):
        """Removes messages that meet a criteria.

        In order to use this command, you must have Manage Messages permissions.
        Note that the bot needs Manage Messages as well. These commands cannot
        be used in a private message.

        When the command is done doing its work, you will get a message
        detailing which users got removed and how many messages got removed.
        """

        if ctx.invoked_subcommand is None:
            help_cmd = self.bot.get_command('help')
            await ctx.invoke(help_cmd, command='remove')

    async def do_removal(self, ctx, limit, predicate, *, before=None, after=None):
        if limit > 2000:
            return await ctx.send(f'Too many messages to search given ({limit}/2000)')

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        try:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
        except discord.Forbidden as e:
            return await ctx.send('I do not have permissions to delete messages.')
        except discord.HTTPException as e:
            return await ctx.send(f'Error: {e} (try a smaller search?)')

        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

        to_send = '\n'.join(messages)

        if len(to_send) > 2000:
            await ctx.send(f'Successfully removed {deleted} messages.', delete_after=10)
        else:
            await ctx.send(to_send, delete_after=10)

    @remove.command()
    async def embeds(self, ctx, search=100):
        """Removes messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))

    @remove.command()
    async def files(self, ctx, search=100):
        """Removes messages that have attachments in them."""
        await self.do_removal(ctx, search, lambda e: len(e.attachments))

    @remove.command()
    async def images(self, ctx, search=100):
        """Removes messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @remove.command(name='all')
    async def _remove_all(self, ctx, search=100):
        """Removes all messages."""
        await self.do_removal(ctx, search, lambda e: True)

    @remove.command()
    async def user(self, ctx, member: discord.Member, search=100):
        """Removes all messages by the member."""
        await self.do_removal(ctx, search, lambda e: e.author == member)

    @remove.command()
    async def contains(self, ctx, *, substr: str):
        """Removes all messages containing a substring.

        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send('The substring length must be at least 3 characters.')
        else:
            await self.do_removal(ctx, 100, lambda e: substr in e.content)

    @remove.command(name='bot')
    async def _bot(self, ctx, prefix=None, search=100):
        """Removes a bot user's messages and messages with their optional prefixes."""

        def predicate(m):
            return m.author.bot or (prefix and m.content.startswith(prefix))

        await self.do_removal(ctx, search, predicate)

    @remove.command(name='emoji')
    async def _emoji(self, ctx, search=100):
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r'<:(\w+):(\d+)>')

        def predicate(m):
            return custom_emoji.search(m.content)

        await self.do_removal(ctx, search, predicate)

    @remove.command(name='reactions')
    async def _reactions(self, ctx, search=100):
        """Removes all reactions from messages that have them."""

        if search > 2000:
            return await ctx.send(f'Too many messages to search for ({search}/2000)')

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(f'Successfully removed {total_reactions} reactions.')

    @remove.command(hidden=True)
    async def custom(self, ctx, *, args: str):
        """A more advanced purge command.

        This command uses a powerful "command line" syntax.
        Most options support multiple values to indicate 'any' match.
        If the value has spaces it must be quoted.

        The messages are only deleted if all options are met unless
        the `--or` flag is passed, in which case only if any is met.

        The following options are valid.

        `--user`: A mention or name of the user to remove.
        `--contains`: A substring to search for in the message.
        `--starts`: A substring to search if the message starts with.
        `--ends`: A substring to search if the message ends with.
        `--search`: How many messages to search. Default 100. Max 2000.
        `--after`: Messages must come after this message ID.
        `--before`: Messages must come before this message ID.

        Flag options (no arguments):

        `--bot`: Check if it's a bot user.
        `--embeds`: Check if the message has embeds.
        `--files`: Check if the message has attachments.
        `--emoji`: Check if the message has custom emoji.
        `--reactions`: Check if the message has reactions
        `--or`: Use logical OR for all options.
        `--not`: Use logical NOT for all options.
        """
        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--user', nargs='+')
        parser.add_argument('--contains', nargs='+')
        parser.add_argument('--starts', nargs='+')
        parser.add_argument('--ends', nargs='+')
        parser.add_argument('--or', action='store_true', dest='_or')
        parser.add_argument('--not', action='store_true', dest='_not')
        parser.add_argument('--emoji', action='store_true')
        parser.add_argument('--bot', action='store_const', const=lambda m: m.author.bot)
        parser.add_argument('--embeds', action='store_const', const=lambda m: len(m.embeds))
        parser.add_argument('--files', action='store_const', const=lambda m: len(m.attachments))
        parser.add_argument('--reactions', action='store_const', const=lambda m: len(m.reactions))
        parser.add_argument('--search', type=int, default=100)
        parser.add_argument('--after', type=int)
        parser.add_argument('--before', type=int)

        try:
            args = parser.parse_args(shlex.split(args))
        except Exception as e:
            await ctx.send(str(e))
            return

        predicates = []
        if args.bot:
            predicates.append(args.bot)

        if args.embeds:
            predicates.append(args.embeds)

        if args.files:
            predicates.append(args.files)

        if args.reactions:
            predicates.append(args.reactions)

        if args.emoji:
            custom_emoji = re.compile(r'<:(\w+):(\d+)>')
            predicates.append(lambda m: custom_emoji.search(m.content))

        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except Exception as e:
                    await ctx.send(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = all if not args._or else any

        def predicate(m):
            r = op(p(m) for p in predicates)
            if args._not:
                return not r
            return r

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        await self.do_removal(ctx, args.search, predicate, before=args.before, after=args.after)

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nickpoo(self, ctx, target: discord.Member):
        """Allows a moderator to change a users server side nickname to the poo emoji"""
        await target.edit(nick="\U0001f4a9")
        await ctx.send("Nickname changed successfully")

    @commands.command(hidden=True, aliases=['give'])
    async def donate(self, ctx, amount: int):
        """Gives all mentioned users x amount of dollars"""
        for member in ctx.message.mentions:
            member = ctx.get_user_data(member)
            member.wallet += amount
            await member.save()
        await ctx.send("Given {0} :dollar: to {1}".format(amount, [i.display_name for i in ctx.message.mentions]))

    @commands.command(hidden=True)
    async def take(self, ctx, amount: int):
        """Takes x amount of money away from all mentioned users"""
        for member in ctx.message.mentions:
            member = ctx.get_user_data(member)
            member.wallet -= amount
            await member.save()
        await ctx.send("Taken {0} :dollar: from {1}".format(amount, [i.display_name for i in ctx.message.mentions]))

    @commands.command(name="createinvite")
    @commands.bot_has_permissions(create_instant_invite=True)
    async def create_invite(self, ctx, max_age: int = 0, max_uses: int = 0, temp: bool = False, unique: bool = True,
                            reason="Created invite via bot"):
        """
        creates an invite for the channel it was used in. By default its perma
        """
        new_invite = await ctx.channel.create_invite(
            max_age=max_age,
            max_uses=max_uses,
            temp=temp,
            unique=unique,
            reason=reason
        )
        await ctx.send(f"Created invite:\n"
                       f"url: <{new_invite.url}>")

    @commands.command(name="deleteinvite")
    @commands.bot_has_permissions(create_instant_invite=True)
    async def delete_invite(self, ctx, invite: discord.Invite, *, reason: str = "Deleted invite via bot"):
        """Deletes a specific invite"""
        await invite.delete(reason=reason)
        await ctx.send("Invite deleted", delete_after=5)

    @commands.command(name="voicemute")
    @commands.bot_has_permissions(mute_members=True)
    async def mute_user(self, ctx, target: discord.Member):
        """Mutes a target user"""
        await target.edit(mute=True)
        await ctx.send(f"{target} has been muted")

    @commands.command(name="voiceunmute")
    @commands.bot_has_permissions(mute_members=True)
    async def unmute_user(self, ctx, target: discord.Member):
        """Unmutes a target user"""
        await target.edit(mute=False)
        await ctx.send(f"{target} has been unmuted")

    @commands.command(name="subonly", hidden=True, enabled=False)
    async def subonly(self, ctx, role: discord.Role):
        pass

    @commands.command(name="chblock")
    @commands.bot_has_permissions(manage_roles=True)
    async def block_user(self, ctx, member: discord.Member):
        """Blocks a user from sending and reading to this channel"""
        await ctx.channel.set_permissions(member, read_messages=False, send_messages=False,
                                          reason=f"{member} blocked from {ctx.channel} by {ctx.author}")
        await ctx.message.add_reaction("\U00002611")

    @commands.command(name="chunblock")
    @commands.bot_has_permissions(manage_roles=True)
    async def unblock_user(self, ctx, member: discord.Member):
        """Unblocks a user, allowing them to send messages in this channel again"""
        await ctx.channel.set_permissions(member, overwrite=None,
                                          reason=f"{member} unblocked from {ctx.channel} by {ctx.author}")
        await ctx.message.add_reaction("\U00002611")

    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unbanall(self, ctx):
        """Unbans every single user. Both the author and the bot need Ban members permission to use"""
        banned_users = await ctx.guild.bans()
        for user in banned_users:
            await ctx.guild.unban(user, reason="Mass Unban")
        await ctx.send("All members successfully unbanned.")


def setup(bot):
    bot.add_cog(Mod(bot))
