import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
import random


class Giveaway:
    def __init__(self, bot):
        self.bot = bot
        self.giveaways = {}

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        return ctx.guild is not None

    @commands.command(aliases=["startgiveaway", 'startgw'])
    @commands.has_permissions(manage_messages=True)
    async def opengiveaway(self, ctx):
        """Opens a giveaway

        The bot will send a message and everyone who reacts to the message is entered. Each user can only enter once
        regardless of how many reactions they add. Each person can only host 1 giveaway at a time per guild.

        """
        if ctx.guild not in self.giveaways:
            self.giveaways[ctx.guild] = {}
            message = await ctx.send("**Giveaway open, everyone who reacts to this message with any reaction "
                                     "is entered, each user is only counted once**")
            self.giveaways[ctx.guild][ctx.author] = message
        elif ctx.author in self.giveaways[ctx.guild]:
            await ctx.send(
                "I can only hold 1 giveaway per person, end your current giveaway to start a new one")

    @commands.command(aliases=['stopgiveaway', 'stopgw'])
    @commands.has_permissions(manage_messages=True)
    async def closegiveaway(self, ctx):
        """Closes the giveaway, you can only close your own giveaways. This does used for preventing further entries"""
        if ctx.author in self.giveaways[ctx.ctx.guild]:
            updated_message = await ctx.channel.get_message(self.giveaways[ctx.guild][ctx.author].id)
            entered_users = []
            for reaction in updated_message.reactions:
                users = await reaction.users().flatten()
                entered_users.extend(users)
            self.giveaways[ctx.author] = entered_users
            try:
                await updated_message.clear_reactions()
            except discord.Forbidden:
                pass
            await ctx.send("Giveaway closed,any reactions added now will no longer count")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def giveawaychoose(self, ctx):
        """Chooses from the pool of entries and announces the winner. You can keep using this command"""
        if ctx.author in self.giveaways[ctx.guild]:
            await ctx.send(f"Congratulations: {random.choice(self.giveaways[ctx.author]).mention}!")


def setup(bot):
    bot.add_cog(Giveaway(bot))
