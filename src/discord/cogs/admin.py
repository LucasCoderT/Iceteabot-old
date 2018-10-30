import inspect

from src.discord.utils.permissions import *
from src.helpers import formats


class Admin:
    def __init__(self, bot):
        self.bot = bot

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        return any([await bot_administrator(ctx), await guild_administrator(ctx), await ctx.bot.is_owner(ctx.author)])

    @commands.command(hidden=True, aliases=['grantmod'])
    async def bestowmod(self, ctx):
        """Grants mod permissions to all mentioned users
        can only be used by admins or above"""
        for member in ctx.message.mentions:
            mymember = await ctx.bot.icethinkdb.get_member(member.id)
            if mymember.permissions.moderator:
                await ctx.send(f"{ctx.author.mention} is already a mod")
            else:
                mymember.permissions.moderator = True
                await mymember.save()
                await ctx.send(
                    f"{member.mention} has been promoted to Moderator status, use your new power with great pride. :)")

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        entries = [(attr.replace('_', ' ').title(), val) for attr, val in permissions]
        await formats.entry_to_code(ctx, entries)

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def botpermissions(self, ctx):
        """Shows the bot's permissions.
        This is a good way of checking if the bot has the permissions needed
        to execute the commands it wants to execute.
        To execute this command you must have Manage Roles permissions.
        You cannot use this in private messages.
        """
        channel = ctx.message.channel
        member = ctx.message.server.me
        await self.say_permissions(ctx, member, channel)

    @commands.command(name="newrole", aliases=['createrole'])
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def new_role(self, ctx, role_name: str, role_color: discord.Colour):
        new_role = await ctx.guild.create_role(name=role_name, colour=role_color,
                                               permissions=None,
                                               reason=f"Role created by new_role command invoked by {ctx.author.display_name}",
                                               mentionable=True)
        if new_role is not None:
            await ctx.send(f"Role {role_name} has been created successfully")

    @commands.command(name="deleterole")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def delete_role(self, ctx, target_role: discord.Role = None):
        """Deletes a specific role"""
        if target_role is not None:
            await target_role.delete(reason=f"Role deleted by {ctx.author} via the delete_role command")
            await ctx.send("Role deleted successfully", delete_after=5)

    @commands.command(name="addrole")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def add_role(self, ctx, target_role: discord.Role):
        """Adds a role to all mentioned users"""
        if target_role is not None:
            for member in ctx.message.mentions:
                await member.add_roles(
                    reason=f"Added {ctx.author.display_name} to role {target_role.name} via the add_role command",
                    *[target_role])
        await ctx.send(f"Added {len(ctx.message.mentions)} members to the role {target_role.name}")

    @commands.command(name="gblacklist", aliases=['block'])
    async def black_list(self, ctx, member: discord.Member):
        """Globally blacklist a user from using the bot"""
        if member == ctx.author:
            return await ctx.send("You cannot blacklist yourself :thinking:")
        if member.bot:
            return await ctx.send("Bots are already globally blacklisted")
        await ctx.bot.icethinkdb.add_black_list(member)
        await ctx.send(f"{member.display_name} has been blacklisted, I will now ignore any commands they use.")

    @commands.command(name="gunblock")
    async def un_block(self, ctx, member: discord.Member):
        """Unblocks a user from the bot's global blacklist"""
        try:
            if member.id in ctx.bot.black_list:
                await ctx.bot.icethinkdb.remove_black_list(member)
                await ctx.send(f"{member.display_name} unblocked")
            else:
                return await ctx.send(f"{member.display_name} is not blacklisted")
        except:
            await ctx.send("unable to unblock member")

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def add_bottester(self, ctx, member: discord.Member):
        try:
            bot_tester_role = discord.utils.get(ctx.guild.roles, name="bot_testers")
            await member.add_roles(bot_tester_role)
            await ctx.send(f"added {member.display_name}")
        except:
            await ctx.send("Failure")

    @commands.command(name="gtoggle")
    async def toggle_cmd(self, ctx, *, command: str):
        """Globally enables/disables a specified command."""
        command_obj = self.bot.get_command(command)
        if command_obj is not None:
            command_obj.enabled = not command_obj.enabled
            await ctx.send(
                f"Command **{command_obj.name}** has been sucessfully "
                f"**{'enabled' if command_obj.enabled else 'disabled'}**")
        else:
            await ctx.send("Command was not found")

    @commands.command(name="commandhistory", aliases=['cmdhistory'])
    @commands.guild_only()
    async def command_history(self, ctx, amount: int = 5):
        """Displays a embed displaying the most recently used commands in the guild."""
        paginator = await CommandHistoryPaginator.get_command_history(ctx, amount)
        await paginator.paginate()


def setup(bot):
    bot.add_cog(Admin(bot))
