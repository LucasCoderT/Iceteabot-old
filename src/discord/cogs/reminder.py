import discord
from discord.ext import commands

from src.discord.utils import time
from src.discord.utils.iceteacontext import IceTeaContext
from src.discord.utils.nextgen import Reminder as ReminderDTO


class Reminder:
    """Reminders to do something."""

    def __init__(self, bot):
        self.bot = bot

    def __str__(self):
        return self.__class__.__name__

    async def on_reminder_complete(self, timer: ReminderDTO):
        if not timer.private:
            channel = self.bot.get_channel(timer.channel)
            if channel is not None:
                author = channel.guild.get_member(timer.user)
                if all([channel, author]):
                    await channel.send(
                        f"{author.mention}, {timer.human_delta} you asked to be reminded of:\n{timer.message}")
        else:
            channel = self.bot.get_user(timer.user)
            if channel is not None:
                await channel.send(
                    f"{channel.mention}, {timer.human_delta} you asked to be reminded of:\n{timer.message}")
        await timer._dto.delete_reminder(timer.id)

    async def create_timer(self, ctx, when, event):
        """Creates a timer.
        Parameters
        -----------
        ctx : IceTeaContext
            The CTX of the command
        when: object
            When the timer should fire.
        event: str
            The event that will be dispatched on completion

        Note
        ------
        Arguments and keyword arguments must be JSON serializable.
        Returns
        --------
        :class:`ReminderDTO`
        """
        reminder: ReminderDTO = await ctx.bot.dto.get(ReminderDTO,
                                                      {"message": when.arg, "timestamp": ctx.message.created_at,
                                                       "channel": ctx.channel.id, "delta": when.dt, "event": event,
                                                       "private": not ctx.guild}, user=ctx.author.id, create=True)
        await reminder.start()
        return reminder

    @commands.group(aliases=['timer', 'remind'], usage='<when>', invoke_without_command=True)
    async def reminder(self, ctx, *, when: time.UserFriendlyTime(commands.clean_content, default='something')):
        """Reminds you of something after a certain amount of time.
        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:
        - "next thursday at 3pm do something funny"
        - "do the dishes tomorrow"
        - "in 3 days do the thing"
        - "2d unmute someone"
        Times are in UTC.
        """

        data = await self.create_timer(ctx, when, "reminder_complete")
        if data:
            delta = time.human_timedelta(when.dt, source=ctx.message.created_at)
            await ctx.send(f"Alright {ctx.author.mention}, I'll remind you about {when.arg} in {delta}.")

    @reminder.error
    async def reminder_error(self, ctx, error):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.send(str(error))

    @reminder.command(name="list")
    async def reminder_list(self, ctx):
        """Shows the user's 5 latest currently runny reminders that are within a day of expiring"""
        reminders = await ctx.bot.fetch_data(f"users/{ctx.author.id}/reminders")
        guild_reminders = []
        for remind in reminders:
            reminder_channel = discord.utils.get(ctx.guild.channels, id=remind['channel'])
            if reminder_channel:
                guild_reminders.append(ReminderDTO(ctx.bot, **remind))
        if len(guild_reminders) == 0:
            return await ctx.send("No active reminders")
        else:
            e = discord.Embed(colour=discord.Colour.blurple(), title='Reminders')
            for reminder in sorted(set(guild_reminders), key=lambda re: re.delta, reverse=True):
                e.add_field(name=f"In {time.human_timedelta(reminder.delta)} - ID: {reminder.id}",
                            value=reminder.message,
                            inline=False)
            await ctx.send(embed=e)

    @reminder.command(name="delete")
    async def delreminder(self, ctx, rid: int):
        """Deletes a reminder"""
        reminder = await ctx.bot.dto.delete_reminder(rid)
        if reminder:
            await ctx.send("Successfully deleted reminder")


def setup(bot):
    bot.add_cog(Reminder(bot))
