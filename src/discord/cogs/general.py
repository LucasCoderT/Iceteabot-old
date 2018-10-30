import asyncio
import random
import re

import discord
from discord.ext import commands
from discord.ext.commands import UserInputError, BucketType

from src.discord.utils.paginator import HelpPaginator
from src.helpers import formats


class TimeParser:
    def __init__(self, argument):
        compiled = re.compile(r"(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?")
        self.original = argument
        try:
            self.seconds = int(argument)
        except ValueError as e:
            match = compiled.match(argument)
            if match is None or not match.group(0):
                raise commands.BadArgument('Failed to parse time.') from e

            self.seconds = 0
            hours = match.group('hours')
            if hours is not None:
                self.seconds += int(hours) * 3600
            minutes = match.group('minutes')
            if minutes is not None:
                self.seconds += int(minutes) * 60
            seconds = match.group('seconds')
            if seconds is not None:
                self.seconds += int(seconds)

        if self.seconds < 0:
            raise commands.BadArgument('I don\'t do negative time.')

        if self.seconds > 604800:  # 7 days
            raise commands.BadArgument('That\'s a bit too far in the future for me.')


class General:
    def __init__(self, bot):
        self.bot = bot  # type: commands.Bot

    def __str__(self):
        return self.__class__.__name__

    @commands.command(name="hi", aliases=['hello'])
    async def welcome(self, ctx):
        """Display's a welcome message"""
        await ctx.send(f"Hello! I am a bot made by {ctx.bot.owner}")

    @commands.command(name="hug")
    async def hug(self, ctx, target: discord.Member = None):
        await ctx.send(f"Hello {target.mention if hasattr(target, 'mention') else ctx.author.mention}")

    @commands.command()
    async def flip(self, ctx: commands.Context):
        """Flips a coin"""
        coin = random.choice(["heads", "tails"])
        filepath = f"data/assets/{coin}.png"
        if coin == "heads":
            with open(filepath, "rb") as picture:
                await ctx.send(file=discord.File(fp=picture))
        elif coin == "tails":
            with open(filepath, "rb") as picture:
                await ctx.send(file=discord.File(fp=picture))

    @commands.command()
    async def roll(self, ctx, min: int = 0, max: int = 100):
        """Roll a number between two digits, if empty assumes 1-100"""
        await ctx.send("{0.message.author.mention} has rolled a {1}"
                       .format(ctx, random.randint(min, max)))

    @staticmethod
    async def say_permissions(ctx, member, channel):
        permissions = channel.permissions_for(member)
        entries = [(attr.replace('_', ' ').title(), val) for attr, val in permissions]
        await formats.entry_to_code(ctx, entries)

    @commands.command(name="permissions")
    @commands.guild_only()
    async def _permissions(self, ctx, *, member: discord.Member = None):
        """Shows a member's permissions.
        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """
        channel = ctx.message.channel
        if member is None:
            member = ctx.message.author

        await self.say_permissions(ctx, member, channel)

    @commands.command()
    @commands.cooldown(20, 1)
    async def potato(self, ctx):
        """Displays a fancy potato gif"""
        myrandom = random.randint(0, 50)
        if myrandom < 25:
            with open("data/assets/potato.gif", "rb") as picture:
                await ctx.send(file=discord.File(fp=picture))
        elif myrandom > 25:
            with open("data/assets/bad_potato.gif", "rb") as picture:
                await ctx.send(file=discord.File(fp=picture))

    @commands.command()
    async def pick(self, ctx, choicea, choiceb):
        """Choose between 2 choices"""
        await ctx.send(random.choice([choicea, choiceb]))

    @commands.command()
    async def ping(self, ctx):
        """displays the bot's latency with discord"""
        await ctx.send(f"Current ping is: **{round(ctx.bot.latency,2)} seconds**")

    @commands.command()
    async def suggest(self, ctx, *, suggestion):
        """Adds a suggestion for a bot feature"""
        suggestion_channel = ctx.bot.get_channel(384410040880201730)
        if suggestion_channel is not None:
            embed = discord.Embed()
            embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
            embed.timestamp = ctx.message.created_at
            embed.description = suggestion
            await suggestion_channel.send(embed=embed)
            await ctx.message.add_reaction("\U0001f44d")

    @commands.command(name='help')
    async def _help(self, ctx, *, command: str = None):
        """Shows help about a command for the bot"""
        if command is None:
            p = await HelpPaginator.from_bot(ctx)
        else:
            entity = self.bot.get_cog(command) or self.bot.get_command(command)
            if entity is None:
                clean = command.replace('@', '@\u200b')
                return await ctx.send(f'Command or category "{clean}" not found.')
            elif isinstance(entity, commands.Command):
                p = await HelpPaginator.from_command(ctx, entity)
            else:
                p = await HelpPaginator.from_cog(ctx, entity)

        await p.paginate()

    @commands.command(name="rps", enabled=False, hidden=True)
    async def rpsgame(self, ctx):
        choices = ['rock', 'paper', 'scissors']
        bot_choice = random.randint(0, 2)

        def check(m):
            return m.author == ctx.author and ctx.message.content in ['rock', 'paper', 'scissors']

        response = ctx.bot.wait_for("message", check=check)
        player_decision = choices.index(response.content.lower())

        if player_decision == bot_choice:
            await ctx.send("Its a TIE!")
        elif player_decision > bot_choice or player_decision:
            await ctx.send(f"{ctx.author} WINS!!!")

    @commands.group(invoke_without_command=True)
    @commands.cooldown(60, 1, BucketType.channel)
    async def faq(self, ctx, target: int = None):
        """Display's an embed with the top 20 faqs for the server. FAQs can be added via the subcommand add
        After using this command the user can type a number corresponding to that faq to get the detailed view about it.
        Optionally can provide a number right away to avoid waiting"""
        if len(ctx.guild_data.faqs) == 0:
            return await ctx.send("This guild has no FAQs")
        guild_faqs = sorted(ctx.guild_data.faqs.values(), key=lambda faq: faq.uses)
        try:
            if target is not None:
                target_faq = guild_faqs[target - 1]
                return await target_faq.call(ctx)
        except IndexError:
            return await ctx.send("No faq matching that number")
        embed = discord.Embed(title=f"{ctx.guild} FAQ")
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        embed.description = "".join(
            [f":large_blue_diamond: **{index + 1}**. {question} - **({question.uses} Uses)** - ID: {question.id}" for
             index, question
             in
             enumerate(guild_faqs) if index <= 20])
        message = await ctx.send(embed=embed, content="Select a number")
        try:
            def check(m):
                try:
                    is_author = m.author == ctx.author
                    is_channel = m.channel == ctx.channel
                    is_digit = (int(m.content) - 1) < len(guild_faqs) and (int(m.content) - 1) < 20
                    return all([is_author, is_digit, is_channel])
                except ValueError:
                    return False

            response = await ctx.bot.wait_for("message", check=check, timeout=60)
            target_faq = guild_faqs[int(response.content) - 1]
            await target_faq.call(ctx)
        except asyncio.TimeoutError:
            await message.edit(embed=None, content="Ran out of time", delete_after=15)

    @faq.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, *, question):
        """Registers a FAQ for this server, requires manage server permissions"""
        await ctx.send("Alright, now put the answer")
        answer = await ctx.bot.wait_for("message",
                                        check=lambda
                                            message: ctx.author == message.author and ctx.channel == message.channel)
        new_faq = await ctx.guild_data.add_faq(ctx, question, answer.content)
        if new_faq:
            await ctx.send("Successfully added Question to the FAQ")
        else:
            await ctx.send("Sorry, something went wrong during processing, please try again later", delete_after=15)

    @faq.command(name="delete")
    @commands.has_permissions(manage_guild=True)
    async def deletefaq(self, ctx, *, target):
        """Deletes a FAQ, can use the ID of the faq or the question itself"""
        try:
            response = await ctx.guild_data.delete_faq(target)
            await ctx.send("<a:thumpsup:445250162877661194>")
        except UserInputError as e:
            await ctx.send(e, delete_after=20)


def setup(bot):
    bot.add_cog(General(bot))
