import asyncio
import datetime
import random
import re
import traceback
from collections import Counter

import discord
from discord.ext import commands

from Iceteabot import Iceteabot
from src.discord.utils.nextgen import Guild, User


class BotEvents:
    def __init__(self, bot):
        self.bot: "Iceteabot" = bot

    def __str__(self):
        return self.__class__.__name__

    async def update_discord_bots(self):
        if not self.bot.debug:
            async with self.bot.aioconnection.post(f"https://discordbots.org/api/bots/{self.bot.user.id}/stats/",
                                                   headers={"Authorization": self.bot.config['api_keys']['d_bots']},
                                                   json={"server_count": len(self.bot.guilds)}) as response:
                if response.status == 200:
                    return True

    async def on_command_error(self, ctx: "IceTeaContext", error):
        """Commands error handling method"""
        # Reports that a command is on cool down
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"This command is on cooldown! Hold your horses! >:c\nTry again in **{int(error.retry_after)}** seconds")
        # Reports that the command is disabled
        elif isinstance(error, commands.errors.DisabledCommand):
            await ctx.send("That functionality is currently disabled")
        # Reports that the command cannot be handled inside a PM
        elif isinstance(error, commands.errors.NoPrivateMessage):
            await ctx.send("I am unable to processes this command inside a PM")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Sorry, you forgot to include ``{error.param}`` with that call, try again")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"Sorry, I could not do anything with what you provided me.\n"
                f"You can use ``{ctx.prefix}help {ctx.invoked_with}`` for more info")
        elif hasattr(ctx.cog, f"_{ctx.cog.__class__.__name__}__error"):
            return
        # Reports on non generic errors
        elif isinstance(error, commands.errors.CommandInvokeError):
            try:
                await ctx.message.add_reaction("\U000026a0")

                def check(reaction, reactor):
                    return ctx.message.id == reaction.message.id and reaction.emoji == "\U000026a0" and reaction.count > 1 \
                           and reactor == ctx.bot.owner

                try:
                    await ctx.bot.wait_for("reaction_add", check=check, timeout=30)
                    embed = discord.Embed(color=0xff0000, description='displays detailed error information',
                                          title='Iceteabot error log')
                    embed.add_field(name="Command used", value=f"{ctx.invoked_with}")
                    embed.add_field(name="Command author", value=f"{ctx.message.author.display_name}")
                    embed.add_field(name="args", value=ctx.kwargs or ctx.args)
                    embed.add_field(name="Error", value=error.original, inline=False)
                    embed.add_field(name="Log",
                                    value=f"```py\n{traceback.format_tb(error.original.__traceback__)[-1]}```")
                    embed.timestamp = datetime.datetime.utcnow()
                    debug_channel = ctx.bot.get_channel(360895354033537029)
                    if debug_channel is not None:
                        await debug_channel.send(embed=embed)
                    await ctx.send(embed=embed, delete_after=10)
                    try:
                        await ctx.message.clear_reactions()
                        await ctx.message.delete()
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass
                except asyncio.TimeoutError:
                    try:
                        await ctx.message.clear_reactions()
                        await ctx.message.delete()
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass
            except discord.Forbidden:
                pass

    async def on_member_join(self, member: discord.Member):
        """Creates a welcome message on join and adds them into the database"""
        if not self.bot.data_base_built:
            return
        guild_data: Guild = self.bot.get_guild_data(member.guild.id)
        await self.bot.dto.get(User, id=member.id, create=True)
        if guild_data.role:
            await asyncio.sleep(guild_data.delay)
            role = discord.utils.get(member.guild.roles, id=guild_data.role)
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass
        if guild_data.welcome_channel:
            if not member.bot:
                if guild_data.welcome_message is not None:
                    welcome_channel = member.guild.get_channel(guild_data.welcome_channel)
                    if welcome_channel:
                        await welcome_channel.send(guild_data.welcome_message.format(member))

    async def on_member_remove(self, member: discord.Member):
        """Notifies of a member leaving the server"""
        if not self.bot.data_base_built:
            return
        guild_data: Guild = self.bot.guild_data[member.guild.id]
        if guild_data.leaving_channel:
            if not member.bot:
                channel = member.guild.get_channel(guild_data.leaving_channel)
                if channel is not None:
                    await channel.send(guild_data.leaving_message.format(member))
        try:
            await guild_data.delete_member(member.id)
        except Exception as e:
            pass

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot:
            return

        if not self.bot.data_base_built:
            return

        if before.nick != after.nick and after.nick is not None:
            guild_data = self.bot.get_guild_data(before.guild.id)

            if guild_data.tracking:
                if before.nick != after.nick:
                    member = await guild_data.get_member(before.id)
                    await member.add_nickname(after.nick)

    async def on_guild_join(self, new_guild: discord.Guild):
        if not self.bot.data_base_built:
            return
        self.bot.guild_data[new_guild.id] = await self.bot.dto.get(Guild, guild=new_guild.id, create=True)
        self.bot.guild_commands_used[new_guild.id] = Counter()
        await self.update_discord_bots()

    async def on_guild_remove(self, old_guild: discord.Guild):
        if not self.bot.data_base_built:
            return
        guild_data = self.bot.guild_data.pop(old_guild.id, None)
        if guild_data is not None:
            await guild_data.delete()
            del self.bot.guild_commands_used[old_guild.id]
        await self.update_discord_bots()

    async def on_guild_available(self, guild: discord.Guild):
        new_guild: Guild = self.bot.guild_data.get(guild.id)
        if new_guild:
            new_guild.available = True
            await new_guild.update()

    async def on_guild_unavailable(self, guild: discord.Guild):
        old_guild: Guild = self.bot.guild_data.get(guild.id)
        if old_guild:
            old_guild.available = False
            await old_guild.update()

    async def on_command_completion(self, ctx):
        if ctx.guild is None:
            return
        payload = {
            "command": str(ctx.command.root_parent) or str(ctx.command.name),
            "guild": ctx.guild.id,
            "channel": ctx.channel.id,
            "author": ctx.author.id,
            "called": None,
        }
        await self.bot.post_data(payload, "commandcall")
        if ctx.guild is None:
            return
        self.bot.commands_used[ctx.command.name] += 1
        try:
            ctx.bot.guild_commands_used[ctx.guild][ctx.command] += 1
        except KeyError:
            ctx.bot.guild_commands_used[ctx.guild] = Counter({ctx.command: 1})
        try:
            ctx.prefix_data.uses += 1
            await ctx.prefix_data.update()
        except AttributeError:
            return

    async def on_command(self, ctx):
        if ctx.guild is None:
            return
        if ctx.me.status == discord.Status.idle:
            await ctx.bot.change_presence(activity=discord.Game(name="Waiting for orders"))

    async def on_message(self, message: discord.Message):
        """Responsible for checking every message sent that the bot can see"""
        if message.guild is None:
            self.bot.logger.info(f"{message.author} DM: {message.content}")
            return
        if message.channel.permissions_for(message.guild.me).send_messages:
            if re.search("\(╯°□°）╯︵ ┻━┻", message.content):
                randint = random.randint(0, 100)
                if randint > 10:
                    await message.channel.send(f"{message.author.mention} ┬──┬ ノ( ゜-゜ノ)")
                else:
                    with open("data/assets/table_flip.gif", 'rb') as gif:
                        try:
                            await message.channel.send(file=discord.File(fp=gif))
                        except discord.Forbidden:
                            await message.channel.send(f"{message.author.mention} ┬──┬ ノ( ゜-゜ノ)")

    # async def on_guild_channel_create(self, channel):
    #     async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create):
    #         pass


def setup(bot):
    bot.add_cog(BotEvents(bot))


if __name__ == '__main__':
    from Iceteabot import Iceteabot, IceTeaContext
