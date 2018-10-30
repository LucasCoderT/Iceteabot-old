import asyncio
import typing
import uuid
from collections import Counter
from datetime import datetime

from discord import Embed, RawReactionActionEvent, RawMessageDeleteEvent
from discord.ext import commands

from src.discord.utils.permissions import guild_administrator


class PollObj:
    def __init__(self, **kwargs):
        self.valid_reactions = kwargs.get("valid_reactions")
        self.empty_char = u"\u2591"
        self.filled_char = u"\u2588"
        self.votes = Counter()
        self.title = kwargs.get('title')
        self.options = kwargs.get('options')
        self.total = kwargs.get('total_votes', 0)
        self._new_votes = False
        self.message = kwargs.get('message')
        self.author = kwargs.get('author')
        self.closed = kwargs.get('status', False)
        self.ctx = kwargs.get('ctx')
        self.id = kwargs.get('id')
        self.created = datetime.utcnow()
        self.message_task: asyncio.Task = self.ctx.bot.loop.create_task(self.message_editor_task())

    async def message_editor_task(self):
        while not self.closed:
            if self._new_votes:
                await self.ctx.bot.http.edit_message(self.message.id, self.ctx.channel.id,
                                                     embed=self.embed_builder())
                self._new_votes = False
            await asyncio.sleep(5)
        await self.ctx.bot.http.edit_message(self.message.id, self.ctx.channel.id,
                                             embed=self.embed_builder("Closed"))
        await self.message.clear_reactions()

    def embed_builder(self, status: str = "Open") -> dict:
        embed = Embed(title=self.title)
        embed.set_author(name=self.author.display_name, icon_url=self.author.avatar_url)
        for op, emo in self.options.items():
            percent = self.calculator(emo)
            embed.add_field(name=op, value=f"{emo} : {self.progress_bar(percent)} {percent}%", inline=False)
        embed.set_footer(text=f"Status: {status} | {self.id}")
        return embed.to_dict()

    def calculator(self, emoji: str) -> int:
        try:
            return int(round((self.votes.get(emoji) / sum(self.votes.values()) or 0), 2) * 100)
        except:
            return 0

    def progress_bar(self, percentage) -> str:
        if percentage == 100:
            return f"{self.filled_char * 10}"
        elif 90 <= percentage <= 100:
            return f"{self.filled_char * 9}{self.empty_char * 1}"
        elif 80 <= percentage <= 90:
            return f"{self.filled_char * 8}{self.empty_char * 2}"
        elif 70 <= percentage <= 80:
            return f"{self.filled_char * 7}{self.empty_char * 3}"
        elif 60 <= percentage <= 70:
            return f"{self.filled_char * 6}{self.empty_char * 4}"
        elif 50 <= percentage <= 60:
            return f"{self.filled_char * 5}{self.empty_char * 5}"
        elif 40 <= percentage <= 50:
            return f"{self.filled_char * 4}{self.empty_char * 6}"
        elif 30 <= percentage <= 40:
            return f"{self.filled_char * 3}{self.empty_char * 7}"
        elif 20 <= percentage <= 30:
            return f"{self.filled_char * 2}{self.empty_char * 8}"
        elif 10 <= percentage <= 20:
            return f"{self.filled_char * 1}{self.empty_char * 9}"
        elif 0 <= percentage <= 10:
            return f"{self.empty_char * 10}"


class Poll:
    def __init__(self, bot):
        self.bot = bot
        self.polls = {}  # type: typing.Dict[int,PollObj]
        self.poll_data = {}
        self.valid_reactions = ['\u0031\u20E3', '\u0032\u20E3', '\u0033\u20E3', '\u0034\u20E3',
                                '\u0035\u20E3', '\u0036\u20E3', '\u0037\u20E3', '\u0038\u20E3',
                                '\u0039\u20E3', '\U0001F51F']
        self.empty_char = u"\u2591"
        self.filled_char = u"\u2588"

    def __str__(self):
        return self.__class__.__name__

    def __unload(self):
        for poll in self.polls.values():
            poll.message_task.cancel()

    def reaction_filter(self, payload: RawReactionActionEvent) -> bool:
        if payload.emoji.name not in self.valid_reactions:
            return False
        if self.bot.user.id == payload.user_id:
            return False
        elif payload.message_id not in self.polls:
            return False
        elif self.bot.get_user(payload.user_id).bot:
            return False
        return True

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if self.reaction_filter(payload):
            poll = self.polls[payload.message_id]
            poll.votes[payload.emoji.name] += 1
            poll._new_votes = True

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        if self.reaction_filter(payload):
            poll = self.polls[payload.message_id]
            poll.votes[payload.emoji.name] -= 1
            poll._new_votes = True

    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
        if payload.message_id in self.polls:
            data = self.polls.pop(payload.message_id)
            data.message_task.cancel()

    @commands.command(hidden=True)
    async def _poll_data(self, ctx, arg1, arg2, arg3=None, arg4=None, arg5=None, arg6=None, arg7=None, arg8=None,
                         arg9=None,
                         arg10=None):
        self.poll_data[ctx.message.id] = [arg for arg in [arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10]
                                          if
                                          arg]

    @commands.command()
    @commands.cooldown(30, 1, commands.BucketType.default)
    @commands.bot_has_permissions(add_reactions=True)
    async def cpoll(self, ctx, title, *, data):
        """Creates a poll
        the format of the options must be in: question option1 option2 etc.. Supports up to 10 options
        example:

        <prefix>cpoll "Is Iceteabot awesome?" yes no "maybe so"


        """
        if len(data.split()) > 10:
            await ctx.send("I can only process 10 options MAX")
            return
        else:
            await ctx.invoke(self._poll_data, *data.split())
            pid = str(uuid.uuid4())
            options = dict(zip(self.poll_data[ctx.message.id], self.valid_reactions))
            embed = Embed(title=title)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
            for op, emo in options.items():
                embed.add_field(name=op, value=f"{emo} : {self.empty_char * 10} 0%", inline=False)
            embed.set_footer(text=f"Status: Open | {pid}")
            message = await ctx.send(embed=embed)
            await asyncio.sleep(1)
            for emo in options.values():
                await message.add_reaction(emo)
            self.polls[message.id] = PollObj(
                valid_reactions=self.valid_reactions,
                title=title,
                options=options,
                ctx=ctx,
                author=ctx.author,
                message=message,
                id=pid,
            )
            await ctx.message.delete()

    @commands.command()
    async def dpoll(self, ctx, poll_id):
        """Closes a currently open poll, you can get the ID from the bottom of the poll message embed,
        only the person who opened the poll can close it"""
        polobj = None
        message_id = None
        for message, poll_data in self.polls.items():
            if poll_data.id == poll_id:
                polobj = poll_data
                message_id = message
                break
        if hasattr(poll_id, "author"):
            if polobj.author != ctx.author:
                return
            if all([polobj is not None, message_id is not None]):
                polobj.closed = True
                await asyncio.sleep(3)
                self.polls[message_id].message_task.cancel()
                del self.polls[message_id]
                try:
                    await self.bot.http.clear_reactions(message_id, ctx.channel.id)
                except:
                    pass

    @commands.command()
    @commands.check(guild_administrator)
    async def viewpolls(self, ctx):
        """Views how many currently running polls"""
        await ctx.send(f"currently running **{len(self.polls)}** polls")


def setup(bot):
    bot.add_cog(Poll(bot))
