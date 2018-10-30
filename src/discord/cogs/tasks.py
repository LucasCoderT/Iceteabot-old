from discord.ext import commands

from src.discord.utils.errors import BadTask
from src.discord.utils.paginator import TaskPaginator


class Tasks:
    def __init__(self, bot):
        self.bot = bot

    async def __error(self, ctx, error):
        if isinstance(error, BadTask):
            await ctx.send("Invalid Task number or I cannot find said number")
        else:
            await ctx.send(str(error), delete_after=10)

    @commands.group(invoke_without_command=True)
    async def task(self, ctx):
        if ctx.invoked_subcommand is None:
            help_command = ctx.bot.get_command("help")
            await ctx.invoke(help_command, command="task")

    @task.command(aliases=['create', 'add'])
    async def new(self, ctx, *, content: str):
        """Creates a new task for the user"""
        author_data = await ctx.author_data
        await author_data.add_task(content)
        await ctx.send("Successfully added task")

    @task.group(invoke_without_command=True)
    async def view(self, ctx, number: int = None):
        """Views all your tasks"""
        if number is None:
            help_command = ctx.bot.get_command("help")
            await ctx.invoke(help_command, command="task view")
        else:
            author_data = await ctx.author_data
            paginator = TaskPaginator(ctx, author_data.tasks)
            await paginator.paginate()

    @view.command()
    async def unfinished(self, ctx):
        author_data = await ctx.author_data
        all_tasks = [task for task in author_data.tasks if not task.finished]
        if all_tasks:
            paginator = TaskPaginator(ctx, all_tasks)
            await paginator.paginate()
        else:
            await ctx.send("You have no tasks")

    @view.command()
    async def finished(self, ctx):
        author_data = await ctx.author_data
        all_tasks = [task for task in author_data.tasks if task.finished]
        if all_tasks:
            paginator = TaskPaginator(ctx, all_tasks)
            await paginator.paginate()
        else:
            await ctx.send("You have no tasks")

    @task.command()
    async def delete(self, ctx, number: int):
        """Deletes a task by task number"""
        try:
            await ctx.user_data.delete_task(number)
            await ctx.send("Task sucessfully deleted")
        except BadTask as e:
            await ctx.send(e, delete_after=10)

    @task.command()
    async def finish(self, ctx, number: int):
        """Marks a task as finished"""
        try:
            author_data = await ctx.author_data
            await author_data.finish_task(number)
            await ctx.send("Task sucessfully finished")
        except Exception as e:
            await ctx.send("No task with that error found")


def setup(bot):
    bot.add_cog(Tasks(bot))
