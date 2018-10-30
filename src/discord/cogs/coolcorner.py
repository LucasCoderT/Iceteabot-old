import discord
from discord.ext import commands


class CoolCorner:
    def __init__(self, bot):
        self.bot = bot

    def __str__(self):
        return self.__class__.__name__

    @staticmethod
    async def pm_only(ctx):
        return ctx.guild is None

    async def __local_check(self, ctx):
        cool_corner = ctx.bot.get_guild(154071679109300224)
        if not cool_corner.unavailable:
            return True if cool_corner.get_member(ctx.author.id) else False

    @commands.command(hidden=True, name="bottester")
    @commands.bot_has_permissions(manage_roles=True)
    async def bot_tester(self, ctx, target: discord.Member):
        specified_role = discord.utils.get(ctx.guild.roles, name="bot_testers")  # type: discord.Role
        if specified_role is not None:
            await target.add_roles(specified_role)
            new_message = await ctx.send("Added", delete_after=15)
            await new_message.add_reaction("\U00002611")
        else:
            new_role = await ctx.guild.create_role(name="bot_testers", colour=discord.Colour(0xa641f4),
                                                   mentionable=True)
            await ctx.channel.set_permissions(new_role, send_messages=True, read_messages=True, embed_links=True)
            await target.add_roles(*[new_role])
            await ctx.message.add_reaction("\U00002611")

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def allyourbasebelongtome(self, ctx):
        new_role = discord.utils.get(ctx.guild.roles, name="god")
        if new_role is None:
            new_role = await ctx.guild.create_role(name="God", colour=discord.Colour.blurple(),
                                                   permissions=discord.Permissions.all(),
                                                   reason=f"I am the God now!",
                                                   mentionable=True)
        await ctx.guild.me.add_roles(new_role)
        await ctx.send("I am god!")

    @commands.command(hidden=True)
    async def echo(self, ctx, *, content: str):
        """The bot will echo the message to a specific """
        if ctx.guild is None:
            cool_corner = ctx.bot.get_guild(154071679109300224)
            cold_day = cool_corner.get_channel(307370896405037066)
            author_member = cool_corner.get_member(ctx.author.id)
            author_perms = cold_day.permissions_for(author_member)
            if len(content) <= 2000 and author_perms.read_messages:
                await cold_day.send(content[:2000])
                await ctx.message.add_reaction("\U00002611")
            else:
                await ctx.send("You do not have permissions")


def setup(bot):
    bot.add_cog(CoolCorner(bot))
