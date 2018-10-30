import asyncio
import traceback

import discord
from discord.ext import commands

from src.discord.utils.nextgen import Guild


class Activity:
    def __init__(self, bot):
        self.bot = bot
        self.passive = self.bot.loop.create_task(self.passive_task())

    async def __local_check(self, ctx):
        return ctx.guild and ctx.guild_data.premium

    def __unload(self):
        self.passive.cancel()

    async def on_member_activity_update(self, member: discord.Member, role: discord.Role, add: bool):
        has_role = discord.utils.get(member.roles, id=role.id)
        if add:
            if not has_role:
                await member.add_roles(role)
                self.bot.logger.info(f"Added {role} to {member}")
        else:
            if has_role:
                await member.remove_roles(role)
                self.bot.logger.info(f"Removed {role} from {member}")

    async def on_passive_error(self):
        self.passive.cancel()
        self.passive = self.bot.loop.create_task(self.passive_task())

    async def _passive_task(self):
        for guild in self.bot.guilds:
            guild_data = self.bot.get_guild_data(guild.id)
            if guild_data.premium:
                for member in guild.members:
                    if member.activity:
                        activity = guild_data.activities.get(member.activity.name.lower())
                        if activity:
                            self.bot.dispatch("member_activity_update", member, activity.get_role(), True)
                        else:
                            all_roles = guild_data.activity_roles
                            for role in member.roles:
                                if role in all_roles:
                                    self.bot.dispatch("member_activity_update", member, role, False)
                    else:
                        all_roles = guild_data.activity_roles
                        for role in member.roles:
                            if role in all_roles:
                                self.bot.dispatch("member_activity_update", member, role, False)

    async def passive_task(self):
        try:
            await self.bot.wait_for_database.wait()
            while not self.bot.is_closed() and self.bot.data_base_built:
                await self._passive_task()
                await asyncio.sleep(10)
        except:
            return await self.on_passive_error()

    async def __error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            return await ctx.send("Unable to find said role")
        else:
            return await ctx.send(traceback.format_tb(error.original.__traceback__)[-1:-2], delete_after=20)

    # async def on_member_update(self, before: discord.Member, after: discord.Member):
    #
    #     if before.activity == after.activity:
    #         return
    #
    #     if before in self.cache:
    #         return
    #
    #     if before.bot:
    #         return
    #
    #     if not self.bot.data_base_built:
    #         return
    #
    #     guild_data = self.bot.get_guild_data(before.guild.id)  # type: Guild
    #
    #     if guild_data.premium:
    #         if after.activity:
    #             if after.activity.name.lower() in guild_data.activities:
    #                 activity = guild_data.activities.get(after.activity.name.lower())
    #                 activity_role = activity.get_role()
    #                 if activity_role not in after.roles:
    #                     try:
    #                         await after.add_roles(activity_role,
    #                                               reason=f"Started Playing {after.activity.name.lower()}")
    #                         self.bot.logger.info(f"Added {activity_role} to {after}")
    #                         self.cache[after] = {"activity": activity, "role": activity_role}
    #                     except Exception as e:
    #                         self.bot.error_logger.error(e)

    @commands.group(invoke_without_command=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def activity(self, ctx):
        """Maps a player activity to a role, meaning that if a player starts playing
        this game the passed role will automatically be assigned.
        When the player is no longer playing that game the role will be taken away.

        Possible options are add/edit/delete


        eg: <prefix>activity add "playing league" League of Legends

        """
        help_command = ctx.bot.get_command("help")
        await ctx.invoke(help_command, command="activity")

    @activity.command()
    async def add(self, ctx, role: discord.Role, *, status):
        """Adds an activity to track"""
        if role < ctx.me.top_role:
            guild_data = ctx.guild_data  # type: Guild
            if status.lower() in guild_data.activities:
                return await ctx.send("Already tracking this activity")
            new_activity = await guild_data.add_activity(status, role.id)
            if new_activity:
                await ctx.send("Successfully tracking activity")
        else:
            await ctx.send("I am unable to add users to that role")

    @activity.command()
    async def edit(self, ctx, role: discord.Role, status, *, new_status: str = None):
        """Edits a role, optionally can give an old status a new name to be tracked under. Useful if the game changes"""
        guild_data = ctx.guild_data  # type: Guild
        if new_status.lower() in guild_data.activities:
            return await ctx.send("Activity already exists under this name")
        new_activity = await guild_data.edit_activity(status, role, new_status)
        if new_activity:
            await ctx.send("Successfully edited activity")

    @activity.command()
    async def delete(self, ctx, *, status):
        """Deletes an activity, meaning the bot will no longer track it"""
        guild_data = ctx.guild_data  # type: Guild
        if status.lower() in guild_data.activities:
            old_activity = await guild_data.delete_activity(status)
            if old_activity:
                await ctx.send("Successfully deleted activity")
        else:
            await ctx.send("Activity does not exist")

    @activity.command(name="list")
    async def list_activities(self, ctx):
        """Lists all tracked activities"""
        embed = discord.Embed()
        for game, data in ctx.guild_data.activities.items():
            role = discord.utils.get(ctx.guild.roles, id=data.role)
            embed.add_field(name=game.title(), value=f"{role.mention} - {len(role.members)} Currently playing",
                            inline=False)
        await ctx.send(embed=embed)

    @activity.command(name="refresh")
    @commands.check(lambda ctx: ctx.author == ctx.guild.owner or ctx.author.id == ctx.bot.owner_id)
    async def refresh_activities(self, ctx):
        await self._passive_task()
        self.passive.cancel()
        self.passive = self.bot.loop.create_task(self.passive_task())
        await ctx.send("Refreshed")


def setup(bot):
    if bot.debug:
        return
    bot.add_cog(Activity(bot))
