import asyncio
import glob
import logging
import os
import typing
import ujson
from collections import Counter
from datetime import datetime

import discord
import psutil
import raven
from aiohttp import ClientSession
from discord.ext import commands
from raven.conf import setup_logging
from raven.handlers.logging import SentryHandler
from raven_aiohttp import AioHttpTransport

from src.discord.utils.iceteacontext import IceTeaContext
from src.discord.utils.nextgen import Guild, User, Command, DiscordDto
from src.discord.utils.paginator import CannotPaginate


class Iceteabot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super(Iceteabot, self).__init__(command_prefix=self.get_guild_prefix, *args, **kwargs)
        self.shard_count = self.shard_count or 1
        self.uptime = datetime.utcnow()
        self.debug = True
        self.version = "3.0.0"
        self.commands_used = Counter()
        self.config = kwargs.get('config')
        self.owner = None
        self.client_id = None
        self.sentry = raven.Client(transport=AioHttpTransport, dsn=self.config.get('sentry'))
        self.sentry_handler = SentryHandler(self.sentry)
        self.sentry_handler.setLevel(logging.ERROR)
        setup_logging(self.sentry_handler)
        self.aioconnection = kwargs.get('aioconnection')  # type: ClientSession
        self.iceteacontext = None  # type: IceTeaContext
        self.prefix_func = self.get_guild_prefix
        self.data_base_built = False
        self.wait_for_database = asyncio.Event(loop=self.loop)
        self.guild_commands_used = {}  # type: typing.Dict[int,typing.Counter]
        self.command_data: typing.Dict[str, Command] = {}
        self.guild_data: typing.Dict[int, Guild] = {}
        self.base_url = self.config.get('base_url')
        self.logger = kwargs.get('logger')  # type: logging.Logger
        self.error_logger = kwargs.get("error_logger")  # type: logging.Logger
        self.add_check(self.guild_black_list)
        self.dto = DiscordDto(self)
        self.fetch_data = self.dto.fetch_data
        self.reminder_task = self.loop.create_task(self.dto.get_all_reminders())  # type: asyncio.Task

    async def close(self):
        await asyncio.sleep(2)
        try:
            await self.aioconnection.close()
        except:
            pass
        self.reminder_task.cancel()
        self.sentry_handler.close()
        await self.dto.cancel_reminders()
        await super().close()

    async def on_message(self, message):
        if all((self.data_base_built, not message.author.bot, message.webhook_id is None)):
            ctx = await self.get_context(message, cls=IceTeaContext)
            if ctx.valid:
                await self.invoke(ctx)

    async def on_error(self, event_method, *args, **kwargs):
        self.error_logger.error(f"{event_method} Raised an error", exc_info=True)

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.cog, f"_{ctx.cog.__class__.__name__}__error"):
            return
        ignored_errors = (
            commands.CommandOnCooldown,
            commands.DisabledCommand,
            commands.NoPrivateMessage,
            commands.MissingRequiredArgument,
            commands.BadArgument,
            KeyError,
            CannotPaginate
        )
        if not isinstance(error, ignored_errors):
            self.error_logger.error(error, exc_info=True)

    @staticmethod
    async def guild_black_list(ctx):
        if ctx.guild is None:
            return True
        return ctx.channel.id not in ctx.guild_data.blocked_channels

    async def post_data(self, data, url=None, base_url=None):
        if url:
            full_url = f"{self.base_url}{url}"
        else:
            full_url = base_url
        async with ClientSession(loop=self.loop,
                                 headers={"Authorization": f"Token {self.config['api_keys']['iceteacity']}"}
                                 ) as session:
            async with session.post(json=data, url=full_url) as response:
                if response.status in [200, 201, 204]:
                    response_data = await response.json()
                    return response_data

    async def load_all_command_settings(self):
        print("Updating command settings........", end="")
        command_data = await self.fetch_data("commands")
        self.command_data = {command['name']: Command(self.dto, **command) for command in command_data}
        for command in self.commands:
            if command.qualified_name not in self.command_data and command.name not in \
                    self.command_data:
                if isinstance(command, commands.Group):
                    parent = Command(self.dto, name=command.qualified_name, documentation=command.help,
                                     aliases=",".join(command.aliases),
                                     cog=command.cog_name)
                    await parent.save()
                    self.command_data[command.qualified_name] = parent
                    for subcommand in command.walk_commands():
                        if subcommand.qualified_name not in self.command_data:
                            sub = Command(self.dto, name=subcommand.qualified_name, documentation=subcommand.help,
                                          aliases=",".join(subcommand.aliases),
                                          cog=subcommand.cog_name)
                            await sub.save()
                            self.command_data[subcommand.qualified_name] = sub
                else:
                    root = Command(self.dto, name=command.name, documentation=command.help,
                                   aliases=",".join(command.aliases),
                                   cog=command.cog_name)
                    await root.save()
                    self.command_data[command.qualified_name] = root
        print("Finished")

    @staticmethod
    async def get_guild_prefix(iceteabot, message):
        if message.guild is None:
            return commands.when_mentioned_or(*iceteabot.config['default_prefix'])(iceteabot, message)
        else:
            guild_data: Guild = iceteabot.guild_data.get(message.guild.id)
            if guild_data.prefixes:
                return commands.when_mentioned_or(*guild_data.prefixes.keys())(iceteabot, message)
            else:
                return commands.when_mentioned(iceteabot, message)

    async def sync_database(self):
        await self.wait_until_ready()
        print("Syncing Database after login.....", end="", flush=True)
        user_chunks = [self.users[i:i + 2000] for i in range(0, len(self.users), 2000)]
        for chunk in user_chunks:
            response = await self.post_data({"data": [{"id": user.id} for user in chunk]}, "users")
            self.logger.info(f"Chunk created : {response}")
        for guild in self.guilds:
            guild: discord.Guild = guild
            self.guild_data[guild.id] = await self.dto.get(Guild, guild=guild.id, create=True)
            self.guild_commands_used[guild.id] = Counter()
        await self.load_all_command_settings()
        application_info = await self.application_info()
        self.owner = application_info.owner
        self.client_id = application_info.id
        self.data_base_built = True
        self.wait_for_database.set()
        await self.change_presence(status=discord.Status.online, activity=discord.Game(name="waiting for orders"))

        print("Finished")
        print("-" * 15)
        print("Successfully logged in as {}".format(self.user.name))
        print("Using version {0} of discordpy".format(discord.__version__))
        print(f"Using {psutil.Process().memory_full_info().uss / 1024 ** 2} of ram")
        print(f"loaded {len(self.extensions)} cogs")
        print("-" * 15)

    def get_guild_data(self, guild_id) -> typing.Optional[Guild]:
        return self.guild_data[guild_id]

    async def get_user_data(self, user_id) -> typing.Optional[User]:
        payload = await self.dto.get(User, id=user_id, create=True)
        return payload

    async def get_command_data(self, name) -> typing.Optional[Command]:
        payload = await self.fetch_data(f"commands/{name}")
        return Command(self.dto, **payload)


async def main():
    try:
        logger = logging.getLogger("discord")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename="data/iceteabot.log", encoding='utf-8', mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)
        error_logger = logging.getLogger("errors")
        error_logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename="data/error.log", encoding='utf-8', mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        error_logger.addHandler(handler)
        startup_extensions = [f"src.discord.cogs.{os.path.basename(ext)[:-3]}"
                              for ext in glob.glob("src/discord/cogs/*.py")]
        with open(os.path.join('data', 'config.json')) as file:
            config = ujson.load(file)
        bot = Iceteabot(config=config, owner_id=92730223316959232, status=discord.Status.idle, logger=logger,
                        error_logger=error_logger)
        bot.remove_command("help")
        for extension in startup_extensions:
            try:
                bot.load_extension(extension)
            except Exception as e:
                exc = '{}: {} on cog: {}'.format(type(e).__name__, e, extension)
                print(exc)
        bot.aioconnection = ClientSession(json_serialize=ujson.dumps, loop=bot.loop)
        bot.loop.create_task(bot.sync_database())

        bot.startup_extensions = startup_extensions
        # await bot.command_to_db()

    except Exception as e:
        raise e
    # Runs the bot
    await bot.start(config['api_keys']['discord'])


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
