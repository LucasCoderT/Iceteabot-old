# Built-in Libs
import asyncio
import copy
import glob
import inspect
import io
import os
import textwrap
import traceback
import ujson
from contextlib import redirect_stdout

import discord
from discord.ext import commands

from src.discord.utils import time


# The owner class, commands here can only be executed by the owner of the bot
class Owner:

    def __init__(self, bot):
        self.bot = bot
        self.log = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'iceteabot.log')
        self.sessions = set()

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        return ctx.author == ctx.bot.owner

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    def get_syntax_error(self, e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    @commands.command(hidden=True, aliases=['status', 'chstat', "chstatus", 'botgame'])
    async def changestatus(self, ctx, *, game):
        """Changes the game the bot is playing
        can only be used by admins"""
        await self.bot.change_presence(game=discord.Game(name=game))
        await ctx.send("Now playing ``{0}``".format(game))

    @commands.command(hidden=True, name='eval')
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            '_guild_id': ctx.guild,
            'message': ctx.message,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                if len(f"{value}{ret}") >= 2000:
                    data = io.StringIO(f"{value}{ret}")
                    await ctx.send("Output too long, sending a file instead",
                                   file=discord.File(fp=data, filename="output.txt"))
                    data.close()
                    del data
                    return
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command(pass_context=True, hidden=True)
    async def repl(self, ctx):
        """Launches an interactive REPL session."""
        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            '_guild_id': ctx.guild,
            'channel': ctx.channel,
            'author': ctx.author,
            '_': None,
        }

        if ctx.channel.id in self.sessions:
            await ctx.send('Already running a REPL session in this channel. Exit it with `quit`.')
            return

        self.sessions.add(ctx.channel.id)
        await ctx.send('Enter code to execute or evaluate. `exit()` or `quit` to exit.')

        def check(m):
            return m.author.id == ctx.author.id and \
                   m.channel.id == ctx.channel.id and \
                   m.content.startswith('`')

        while True:
            try:
                response = await self.bot.wait_for('message', check=check, timeout=10.0 * 60.0)
            except asyncio.TimeoutError:
                await ctx.send('Exiting REPL session.')
                self.sessions.remove(ctx.channel.id)
                break

            cleaned = self.cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()'):
                await ctx.send('Exiting.')
                self.sessions.remove(ctx.channel.id)
                return

            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await ctx.send(self.get_syntax_error(e))
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            try:
                with redirect_stdout(stdout):
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception as e:
                value = stdout.getvalue()
                fmt = f'```py\n{value}{traceback.format_exc()}\n```'
            else:
                value = stdout.getvalue()
                if result is not None:
                    fmt = f'```py\n{value}{result}\n```'
                    variables['_'] = result
                elif value:
                    fmt = f'```py\n{value}\n```'

            try:
                if fmt is not None:
                    if len(fmt) > 2000:
                        await ctx.send('Content too big to be printed.')
                    else:
                        await ctx.send(fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await ctx.send(f'Unexpected error: `{e}`')

    @commands.command(name="chavatar")
    async def avatar(self, ctx, link):
        """Edits the bot's avatar. Can only be used by owner"""
        async with ctx.bot.aioconnection.get(link) as response:
            try:
                await ctx.bot.user.edit(avatar=await response.read())
            except:
                await ctx.send("Unable to use this link")
        await ctx.send("Avatar Changed successfully")

    @commands.command()
    async def botname(self, ctx, name: str = None):
        """Changes the bot's username
        :name the new name to be used"""
        # Edits the bot name using the arg :name:
        await ctx.bot.user.edit(username=name)
        # Responds that the mission was a success
        await ctx.send("Name changed successfully")

    @commands.command(hidden=True, no_pm=True)
    async def botnick(self, ctx, *, name: str = None):
        """Changes the bot's nickname
        :name the new name to be used"""
        # Edits the bot name using the arg :name:
        try:
            await ctx.me.edit(nick=name)
            # Responds that the mission was a success
            await ctx.send("Name changed successfully")
        except discord.Forbidden:
            await ctx.send("I do not have permissions to edit my name :cry:")

    @commands.command(hidden=True, aliases=['grantadmin'])
    async def bestowadmin(self, ctx):
        """Grants all mentioned users admin privileges
        Can only be used by god"""
        for member in ctx.message.mentions:
            mymember = await ctx.bot.icethinkdb.get_member(member.id)
            if mymember.administrator:
                await ctx.send(f"{ctx.author.mention} is already an Admin")
            else:
                setattr(mymember, "administrator", True)
                await mymember.save()
                await ctx.send(
                    f"{member.mention} has been promoted to Administrator status, may god have mercy on our souls.")

    @commands.command(hidden=True)
    async def load(self, ctx, *, cog: str):
        """Loads a module."""
        try:
            ctx.bot.load_extension("src.discord.cogs.{0}".format(cog))
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def unload(self, ctx, *, cog: str):
        """Unloads a module."""
        try:
            ctx.bot.unload_extension("src.discord.cogs.{0}".format(cog))
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(name='reloadall', hidden=True)
    async def _reloadall(self, ctx):
        """Attempts to reload all the cogs at once"""
        for cog in ctx.bot.extensions:
            try:
                ctx.bot.unload_extension(cog)
                ctx.bot.load_extension(cog)
            except Exception as e:
                await ctx.send('\N{PISTOL}')
                await ctx.send('{}: {}'.format(type(e).__name__, e))

    @commands.command(name='viewcogs', hidden=True)
    async def _viewcogs(self, ctx):
        await ctx.send("\n".join(cog.split(".")[2] for cog in ctx.bot.extensions))

    @commands.command(hidden=True, aliases=['shutoff', 'quit', 'logout', 'wq!'])
    async def botshutdown(self, ctx):
        await ctx.send("Bot is shutting down")
        await asyncio.sleep(1)
        await ctx.send("Good-bye...")
        await ctx.bot.logout()

    @commands.command(hidden=True, aliases=['log'], enabled=False)
    async def log_viewer(self, ctx):
        """Displays the log file"""
        with open(self.log, mode='r') as log:
            logfile = log.readlines()
        msg = "```py\n"
        counter = -1
        for line in logfile:
            if counter == -11:
                break
            msg += "{0}\n".format(logfile[counter])
            counter -= 1
        msg += "\n```"
        await ctx.send(msg)

    @commands.command(hidden=True, name="cogstatus", aliases=['cstatus'])
    async def cog_status(self, ctx):
        """Displays all currently loaded cogs"""
        cog_names = [cog.split(".")[2] for cog in ctx.bot.extensions]
        msg = ""
        for ext in [f"src.discord.cogs.{os.path.basename(ext)[:-3]}"
                    for ext in glob.glob("src/discord/cogs/*.py")]:
            msg += f'{ext[:-3]} : {":ballot_box_with_check:" if ext[:-3] in cog_names else ":no_entry_sign:" }\n'
        embed = discord.Embed(description="Cog status", title="Iceteabot Cog Status")
        embed.set_thumbnail(url="http://i.imgur.com/5BFecvA.png")
        embed.add_field(name="Cogs loaded:",
                        value=msg
                        )
        await ctx.send(embed=embed)

    @commands.command(name="reload")
    async def _reload(self, ctx, *, extension):
        try:
            ctx.bot.unload_extension("src.discord.cogs.{0}".format(extension))
            ctx.bot.load_extension("src.discord.cogs.{0}".format(extension))
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(aliases=['do'])
    async def repeatcmd(self, ctx, amount: int, command_name, *, command_args):
        """Repeats X command Y times"""
        command = ctx.bot.get_command(command_name)
        if amount > 20:
            return await ctx.send("You want me to repeat a command more than 20 times? You crazy...")
        if command is not None:
            for x in range(0, amount):
                await ctx.invoke(command, command_args)

    @commands.command(name="leaveguild")
    async def leave_guild(self, ctx, target_guild: int):
        guild_obj = ctx.bot.get_guild(target_guild)
        if guild_obj is not None:
            await guild_obj.leave()
            await ctx.bot.owner.send(f"Left guild {guild_obj.name}")
        else:
            await ctx.bot.owner.send(f"Could not find a guild with that ID")

    @commands.command(name="nuke")
    async def nuke_this_shit(self, ctx):
        """Nukes the bot, and destroys the files"""

    @commands.command(name="updateconfig")
    async def update_config(self, ctx):
        """Updates the bot's config file"""
        with open(os.path.join('data', 'config.json')) as file:
            ctx.bot.config = ujson.load(file)
            await ctx.message.add_reaction('\u2705')

    @commands.command(name="updatedbots")
    async def update_dbots(self, ctx):
        """Sends an update request to discordbots"""
        async with ctx.bot.aioconnection.post("https://discordbots.org/api/bots/180776430970470400/stats",
                                              headers={"Authorization": ctx.bot.config['api_keys']['d_bots']},
                                              json={"server_count": len(ctx.bot.guilds)}) as response:
            if response.status == 200:
                await ctx.message.add_reaction("\u2705")

    @commands.command()
    async def newguilds(self, ctx, *, count=5):
        """Tells you the newest guilds the bot has joined.

        The count parameter can only be up to 50.
        """
        count = max(min(count, 50), 5)
        guilds = sorted(ctx.bot.guilds, key=lambda m: m.me.joined_at, reverse=True)[:count]

        e = discord.Embed(title='New Guilds', colour=discord.Colour.green())

        for guild in guilds:
            body = f'Joined {time.human_timedelta(guild.me.joined_at)}'
            e.add_field(name=f'{guild.name} (ID: {guild.id})', value=body, inline=False)

        await ctx.send(embed=e)

    @commands.command(name="promoteguild")
    async def promote_guild(self, ctx, guild: int):
        """Promotes a guild to premium status"""
        guild_data = self.bot.data_cache['guilds'].get(guild)
        guildobj = discord.utils.get(self.bot.guilds, id=guild)
        if guild_data:
            guild_data.premium = not guild_data.premium
            response = await guild_data.update()
            if response:
                await ctx.send(f"Successfully set {guildobj.name} premium status to {guild_data.premium}")

    @commands.command(enabled=False)
    async def setupemojis(self, ctx):
        if ctx.bot.league_client.cache_loaded:
            try:
                champion_data = copy.copy(ctx.bot.league_client.static_cache['champions'])
                list_of_champions = list(champion_data.values())
                target_guilds = {
                    385251416215781376: list_of_champions[103:153]
                }
                try:
                    for guild_id, champ_lists in target_guilds.items():
                        guild = ctx.bot.get_guild(guild_id)
                        for champion in champ_lists:
                            champ_square = champion.image.full_url
                            async with ctx.bot.aioconnection.get(champ_square) as response:
                                if response.status == 200:
                                    formated_name = champion.name.replace(" ", "").replace(".", "_").replace("'", "_")
                                    new_emoji = await guild.create_custom_emoji(name=formated_name,
                                                                                image=await response.read())
                                    await ctx.send(f"{new_emoji} has been successfully created")
                                    await asyncio.sleep(1.5)
                                else:
                                    continue
                except Exception as e:
                    return await ctx.send(e)
            except Exception as e:
                return await ctx.send(e)

    async def on_raw_reaction_add(self, payload):
        if payload.emoji.is_unicode_emoji() and self.bot.owner is not None:
            if all([payload.channel_id == 384410040880201730, payload.user_id == self.bot.owner.id,
                    str(payload.emoji) == "\U0000274c"]):
                channel = self.bot.get_channel(payload.channel_id)
                if channel is not None:
                    message = await channel.get_message(payload.message_id)
                    if payload.message_id is not None:
                        await message.delete()

    @commands.command(name="cleandb")
    async def scavanagedb(self, ctx):
        async with ctx.typing():
            users_deleted = []
            old_database = list(ctx.bot.data_cache['users'].keys())
            for user in old_database:
                user_obj = ctx.bot.get_user(user)
                if user_obj not in ctx.bot.users:
                    user_data = ctx.bot.data_cache['users'][user]
                    users_deleted.append(user)
                    await user_data.delete()
            for user in users_deleted:
                del ctx.bot.data_cache['users'][user]
            log_file = io.StringIO("{0} has been deleted\n".join([u.id for u in users_deleted]))
            await ctx.bot.owner.send(file=discord.File(log_file, filename="result.txt"))
            del log_file


def setup(bot):
    """Standard setup method for cog"""
    bot.add_cog(Owner(bot))
