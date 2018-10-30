import datetime
from collections import Counter

import discord
import psutil
from discord.ext import commands


class Stats:
    """Bot usage statistics."""

    def __init__(self, bot):
        self.bot = bot
        self.process = psutil.Process()
        self.medals = ["\U0001f947", "\U0001F948", "\U0001F949", "\U0001f3c5", "\U0001f3c5"]

    def __str__(self):
        return self.__class__.__name__

    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1

    @commands.command(hidden=True)
    async def socketstats(self, ctx):
        delta = datetime.datetime.utcnow() - self.bot.uptime
        minutes = delta.total_seconds() / 60
        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes
        embed = discord.Embed(title=f"{ctx.me.display_name}",
                              description=f"{total:,} socket events observed\n ({cpm:.2f}/minute)",
                              colour=discord.Colour.blue())
        for event, value in self.bot.socket_stats.most_common():
            if event is None:
                continue
            percent = round((value / total) * 100, 2)
            embed.add_field(name=event.lower().replace("_", " "), value=f"{value:,} **({percent}%)**")
        await ctx.send(embed=embed)

    def get_bot_uptime(self, *, brief=False):
        now = datetime.datetime.utcnow()
        delta = now - self.bot.uptime
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if not brief:
            if days:
                fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
            else:
                fmt = '{h} hours, {m} minutes, and {s} seconds'
        else:
            fmt = '{h}h {m}m {s}s'
            if days:
                fmt = '{d}d ' + fmt

        return fmt.format(d=days, h=hours, m=minutes, s=seconds)

    @commands.command()
    async def uptime(self, ctx):
        """Tells you how long the bot has been up for."""
        await ctx.send(f'Uptime: **{self.get_bot_uptime()}**')

    @commands.command(name="ram")
    async def ramusage(self, ctx):
        """Displays the bot's current ram usage"""
        memory_usage = psutil.Process().memory_full_info().uss / 1024 ** 2
        await ctx.send(f"{memory_usage:.2f} MiB")

    @commands.command(aliases=['botinfo', 'info'])
    @commands.guild_only()
    async def about(self, ctx):
        """Tells you information about the bot itself."""
        embed = discord.Embed(description="Iceteabot version **{0}**".format(ctx.bot.version))
        embed.title = 'Official Bot Server Invite'
        embed.url = 'https://discord.gg/xJYAD4s'
        embed.colour = ctx.me.top_role.color
        owner = ctx.bot.owner
        embed.set_thumbnail(url=ctx.me.avatar_url)
        guild_commands_used = f"{sum(ctx.bot.guild_commands_used[ctx.guild].values()):,}"
        total_commands_used = f"{sum(ctx.bot.commands_used.values()):,}"
        embed.set_author(name=str(owner), icon_url=owner.avatar_url)

        # statistics
        total_members = sum(len(s.members) for s in ctx.bot.guilds)
        total_online = sum(1 for m in ctx.bot.get_all_members() if m.status != discord.Status.offline)
        unique_members = set(ctx.bot.get_all_members())
        unique_online = sum(1 for m in unique_members if m.status != discord.Status.offline)
        text = sum([len(guild.text_channels) for guild in ctx.bot.guilds])
        voice = sum([len(guild.voice_channels) for guild in ctx.bot.guilds])

        members = f"{total_members:,} total\n{total_online:,} online\n{len(unique_members):,} " \
                  f"unique\n{unique_online:,} unique online"
        embed.add_field(name='Members', value=members)
        embed.add_field(name='Channels', value=f'{text + voice:,} total\n{text:,} text\n{voice:,} Voice')
        embed.add_field(name='Uptime', value=self.get_bot_uptime(brief=True))
        embed.set_footer(text='Made with discord.py version {0}'.format(discord.__version__),
                         icon_url='http://i.imgur.com/5BFecvA.png')
        embed.timestamp = self.bot.uptime

        embed.add_field(name='Servers', value=str(len(self.bot.guilds)))
        embed.add_field(name='Commands Run', value=f"**Guild**: {guild_commands_used}\n"
                                                   f"**Total**: {total_commands_used}")

        memory_usage = psutil.Process().memory_full_info().uss / 1024 ** 2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')
        await ctx.send(embed=embed)

    @commands.command()
    async def invite(self, ctx):
        """Grabs the bot's invite link to share"""
        bot_invite_link = discord.utils.oauth_url(ctx.bot.client_id)
        await ctx.send(f"Invite Link: <{bot_invite_link}>")

    def _get_user(self, ctx, user):
        member = ctx.guild.get_member(int(user))
        if member:
            return member.mention
        else:
            return "N/A"

    async def get_todays_stats(self, ctx):
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        tomorrow = (datetime.datetime.utcnow() + datetime.timedelta(1)).strftime("%Y-%m-%d")
        payload = await self.bot.fetch_data(f"guilds/{ctx.guild.id}/commandcall/by-date",
                                            data={"before": tomorrow, "after": today})
        total_commands_used = 0
        top_commands = Counter()
        top_command_callers = Counter()
        for author, cmdcalls in payload.items():
            total_commands_used += sum(cmdcalls.values())
            top_command_callers[author] += sum(cmdcalls.values())
            for command, usage in cmdcalls.items():
                top_commands[command] += usage
        top_commands_msg = ["{0} : {1} ({2:,} uses)".format(medal, command, top_commands[command]) for medal, command,
                            in
                            zip(self.medals, top_commands)]
        top_command_users_msg = [
            "{0} : {1} ({2:,} uses)".format(medal, self._get_user(ctx, user), count)
            for
            medal, (user, count) in zip(self.medals, top_command_callers.most_common()) if
            ctx.guild.get_member(int(user))]
        return top_commands_msg, top_command_users_msg

    async def get_command_stats(self, ctx, embed):
        payload = await self.bot.fetch_data(f"guilds/{ctx.guild.id}/commandcall/by-user")
        total_commands_used = 0
        top_commands = Counter()
        top_command_callers = Counter()
        for author, cmdcalls in payload.items():
            total_commands_used += sum(cmdcalls.values())
            top_command_callers[author] += sum(cmdcalls.values())
            for command, usage in cmdcalls.items():
                top_commands[command] += usage
        embed.description = f"{total_commands_used:,} Commands Used"
        top_commands_msg = ["{0} : {1} ({2:,} uses)".format(medal, command, uses) for medal, (command, uses)
                            in
                            zip(self.medals, top_commands.most_common())]
        top_command_users_msg = [
            "{0} : {1} ({2:,} uses)".format(medal, self._get_user(ctx, user), count)
            for
            medal, (user, count) in zip(self.medals, top_command_callers.most_common()) if
            ctx.guild.get_member(int(user))]
        return top_commands_msg, top_command_users_msg

    @commands.group(invoke_without_command=True)
    async def stats(self, ctx):
        """Display's command usage stats for the guild"""
        embed = discord.Embed(title=f"{ctx.guild.name} Command Usage Stats")
        top_commands, top_users = await self.get_command_stats(ctx, embed)
        today_commands, today_users = await self.get_todays_stats(ctx)
        embed.add_field(name="Top Commands", value="\n".join(top_commands))
        embed.add_field(name="Top Commands Today", value="\n".join(today_commands or ["N/A"]))
        embed.add_field(name="Top Command Users", value="\n".join(top_users), inline=False)
        embed.add_field(name="Top Command Users Today", value="\n".join(today_users or ['N/A']), inline=False)
        await ctx.send(embed=embed)

    @stats.command(name="global")
    async def _global(self, ctx):
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        tomorrow = (datetime.datetime.utcnow() + datetime.timedelta(1)).strftime("%Y-%m-%d")
        payload = await self.bot.fetch_data(f"commandcall/by-user")
        todays_commands = await self.bot.fetch_data(f"commandcall/by-date", data={"before": tomorrow, "after": today})
        embed = discord.Embed(title=f"Global Command Usage Stats")
        total_commands_used = 0
        top_commands = Counter()
        top_command_callers = Counter()
        top_commands_today = Counter()
        top_commands_today_callers = Counter()
        for author, cmdcalls in todays_commands.items():
            top_commands_today_callers[author] += sum(cmdcalls.values())
            for command, usage in cmdcalls.items():
                top_commands_today[command] += usage
        for author, cmdcalls in payload.items():
            total_commands_used += sum(cmdcalls.values())
            top_command_callers[author] += sum(cmdcalls.values())
            for command, usage in cmdcalls.items():
                top_commands[command] += usage
        embed.description = f"{total_commands_used:,} Commands Used"
        top_commands_msg = ["{0} : {1} ({2:,} uses)".format(medal, command, uses) for medal, (command, uses)
                            in
                            zip(self.medals, top_commands.most_common())]
        top_command_users_msg = [
            "{0} : {1} ({2:,} uses)".format(medal, ctx.bot.get_user(int(user)), command) for
            medal, (user, command) in zip(self.medals, top_command_callers.most_common()) if
            ctx.bot.get_user(int(user))]
        top_commands_today_msg = ["{0} : {1} ({2:,} uses)".format(medal, command, uses) for medal, (command, uses)
                                  in
                                  zip(self.medals, top_commands_today.most_common())]
        top_commands_today_users_msg = [
            "{0} : {1} ({2:,} uses)".format(medal, self.bot.get_user(int(user)), uses) for
            medal, (user, uses)
            in
            zip(self.medals, top_commands_today_callers.most_common()) if ctx.bot.get_user(int(user))]
        embed.add_field(name="Top Commands", value="\n".join(top_commands_msg))
        embed.add_field(name="Top Command Users", value="\n".join(top_command_users_msg))
        embed.add_field(name="Top Commands Today", value="\n".join(top_commands_today_msg or ["N/A"]), inline=False)
        embed.add_field(name="Top Command Callers Today", value="\n".join(top_commands_today_users_msg or ["N/A"]))
        await ctx.send(embed=embed)


def setup(bot):
    bot.socket_stats = Counter()
    bot.add_cog(Stats(bot))
