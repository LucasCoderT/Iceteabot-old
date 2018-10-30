import asyncio
import datetime
import logging
import typing
import ujson

import aiohttp
import dateutil.parser
from aiohttp import ClientSession

from src.discord.utils import time
from src.discord.utils.permissions import *


def parse_date(arg):
    if isinstance(arg, datetime.datetime):
        return arg
    if not arg:
        return
    try:
        data = dateutil.parser.parse(arg)
        return data.replace(tzinfo=None)
    except:
        return


def parse_command_channels(arg):
    try:
        data = arg.split(",")
        if data:
            return [int(channel) for channel in data]
    except:
        return arg


class DiscordDto:
    POST_URL = ""
    PRIMARY_KEY = "id"
    IGNORED_FIELDS = ("member", "author", "blocker", "user")

    __slots__ = ("_bot", "_token", "_base_url", "_reminders", "_all_reminders")

    def __init__(self, bot):
        self._bot: "Iceteabot" = bot
        self._token: str = bot.config['api_keys']['iceteacity']
        self._base_url: str = bot.base_url
        self._reminders: typing.Dict[int: Reminder] = {}

    def __eq__(self, other):
        return getattr(self, self.PRIMARY_KEY, None) == other

    @property
    def bot(self) -> "Iceteabot":
        try:
            return self._dto._bot
        except AttributeError:
            return self._bot

    @property
    def token(self) -> str:
        try:
            return self._dto._token
        except AttributeError:
            return self._token

    @property
    def base_url(self) -> str:
        try:
            return self._dto._base_url
        except AttributeError:
            return self._base_url

    @property
    def logger(self):
        return self.bot.error_logger

    @property
    def url(self) -> str:
        return f"{self.bot.base_url}{self.POST_URL.format(discord_id=getattr(self,'_discord_id',None),**self.data)}"

    @classmethod
    def purl(cls, base_url: str, **data) -> str:
        list_url = cls.POST_URL.rsplit("/")
        return f"{base_url}{'/'.join(list_url[0:len(list_url) - 1])}".format(**data)

    @property
    def data(self) -> dict:
        response_data = {}
        for attr in self.__slots__:
            if not attr.startswith("_"):
                data = getattr(self, attr, None)
                if data:
                    response_data[attr] = data
        return response_data

    async def fetch_data(self, url: str, base_url: str = None, data: dict = None) \
            -> typing.Union[typing.Dict, typing.List]:
        return_data = []
        if url:
            full_url = f"{self.bot.base_url}{url}"
        else:
            full_url = base_url
        next_page = None
        async with ClientSession(loop=self.bot.loop,
                                 headers={"Authorization": f"Token {self.token}"},
                                 json_serialize=ujson.dumps) as session:
            async with session.get(f"{full_url}", params=data) as response:
                if response.status == 200:
                    data = await response.json()
                    if "results" in data:
                        return_data.extend(data['results'])
                        if data.get("next") is not None:
                            next_page = data['next']
                    else:
                        return data
        if next_page is not None:
            return_data.extend(await self.fetch_data(url, base_url=next_page))
        return return_data

    async def get(self, obj: "DiscordDto()", post_data: dict = None, create: bool = False, **kwargs) -> "API()":
        post_data = post_data or {}
        try:
            url = obj.POST_URL.format_map(kwargs)
            payload = await self.fetch_data(url, data=post_data)
            if payload:
                return obj(getattr(self, "_dto", self), **payload)
            else:
                raise KeyError
        except KeyError:
            if create:
                post_data.update(kwargs)
                new_obj = obj(getattr(self, "_dto", self), **post_data)
                response = await new_obj.save()
                if response:
                    return new_obj

    async def get_all(self, obj: "DiscordDto()", post_data: dict = None, **kwargs):
        payload = await self.fetch_data(url=obj.purl(self.base_url, **kwargs), data=post_data)
        return [obj(self, **data) for data in payload]

    async def get_guild_data(self, guild_id) -> typing.Optional["Guild"]:
        payload = await self.fetch_data(f"guilds/{guild_id}")
        return Guild(self, **payload)

    async def get_user_data(self, user_id) -> typing.Optional["User"]:
        payload = await self.fetch_data(f"users/{user_id}")
        return User(self, **payload)

    async def get_command_data(self, name) -> typing.Optional["Command"]:
        payload = await self.fetch_data(f"commands/{name}")
        return Command(self, **payload)

    async def get_all_reminders(self):
        await self._bot.wait_for_database.wait()
        while not self._bot.is_closed():
            self._reminders.clear()
            reminders = await self.fetch_data("reminders")
            for reminder in reminders:
                r = Reminder(self, **reminder)
                self._reminders[r.id] = r
                self._bot.loop.create_task(r.start())
            await asyncio.sleep(300)

    async def delete_reminder(self, rid):
        reminder: Reminder = self._reminders.pop(rid, None)
        if reminder:
            reminder.cancel()
            await reminder.delete()
            return reminder

    async def cancel_reminders(self):
        for reminders in self._reminders.values():
            for r in reminders:
                r.cancel()


class API(DiscordDto):
    async def update(self, url=None) -> bool:
        async with aiohttp.ClientSession(
                headers={"Authorization": f"Token {self.token}"},
                json_serialize=ujson.dumps) as session:
            async with session.put(data=self.data, url=url or self.url) as response:
                if response.status == 200:
                    data = await response.json()
                    for attr in data:
                        if attr not in self.IGNORED_FIELDS:
                            setattr(self, attr, data[attr])
                    return True
                else:
                    self.logger.error(
                        f"Update Failed on object: {self.__class__.__name__}  with response : {response.status}",
                        exc_info=True)
                    return False

    async def save(self, url=None) -> bool:
        async with aiohttp.ClientSession(
                headers={"Authorization": f"Token {self.token}"},
                json_serialize=ujson.dumps) as session:
            async with session.post(data=self.data, url=url or self.purl(self.base_url, **self.data)) as response:
                if response.status in [200, 201, 204]:
                    if getattr(self, self.PRIMARY_KEY, None) is None:
                        data = await response.json()
                        setattr(self, self.PRIMARY_KEY, data.get(self.PRIMARY_KEY, None))
                        for attr in data:
                            if hasattr(self, attr) and attr not in self.IGNORED_FIELDS:
                                setattr(self, attr, data[attr])
                    return True
                else:
                    message = await response.text()
                    self.logger.error(
                        f"Save Failed on object: {self.__class__.__name__}  "
                        f"with response : {response.status} with message : {message}",
                        exc_info=True)
                    return False

    async def delete(self, url=None) -> bool:
        async with aiohttp.ClientSession(
                headers={"Authorization": f"Token {self.token}"},
                json_serialize=ujson.dumps) as session:
            async with session.delete(url=url or self.url) as response:
                if response.status in [200, 201, 204]:
                    return True
                elif response.status == 404:
                    return True
                else:
                    try:
                        self.logger.error(
                            f"Delete Failed on object: {self.__class__.__name__} on url : {url} "
                            f" with response : {response.status}",
                            exc_info=True)
                    except aiohttp.ClientResponseError as e:
                        self.logger.exception(e)
                    return False


class Reminder(API):
    __slots__ = (
        "id", "user", "message", "timestamp", "channel", "event", "delta", "private", "expires", "_task", "_short")

    POST_URL = "users/{user}/reminders/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.user = kwargs.pop('discord_id', None)
        self.message = kwargs.pop('message', None)
        self.timestamp = parse_date(kwargs.pop('timestamp', None))
        self.channel = kwargs.pop('channel', None)
        self.event = kwargs.pop('event', None)
        self.delta = parse_date(kwargs.pop('delta', None))
        self.private = kwargs.pop("private", False)
        self.expires = parse_date(kwargs.pop('expires', None))
        self._task = None  # type: asyncio.Task
        self._short = False
        self._dto = dto

    def __hash__(self):
        return hash(self.id)

    @property
    def task(self):
        return self._task

    @task.setter
    def task(self, value):
        self._task = value

    @property
    def short(self):
        return self._short

    @short.setter
    def short(self, value):
        self._short = value

    @property
    def human_delta(self):
        return time.human_timedelta(self.timestamp)

    async def start(self, create: bool = False):
        delta = (self.delta - datetime.datetime.utcnow()).total_seconds()
        if create and delta > 300:
            await self.save()
        else:
            self.bot.loop.create_task(self._task_func())

    async def _task_func(self):
        if self.delta < datetime.datetime.utcnow():
            return await self.delete()
        difference = self.delta - datetime.datetime.utcnow()
        await asyncio.sleep(difference.total_seconds())
        self._dto.delete_reminder(self.id)
        self.bot.dispatch(self.event, self)

    def cancel(self):
        if self.task:
            return self.task.cancel()


class ScheduledCommand:
    __slots__ = ("_bot", "ctx", "command", "when", "_task")

    def __init__(self, bot, ctx, command, when):
        self._bot = bot
        self.ctx = ctx
        self.command = command
        self.when = when
        self._task = bot.loop.create_task(self.schedule_command())

    async def schedule_command(self):
        if self.when < datetime.datetime.utcnow():
            pass
        while self.when > datetime.datetime.utcnow():
            difference = self.when - datetime.datetime.utcnow()
            await asyncio.sleep(difference.total_seconds() - 30)
        self._bot.dispatch("scheduled_command", self)

    def cancel(self):
        if self._task:
            return self._task.cancel()


class Command(API):
    __slots__ = ("name", "documentation", "cog", "aliases", "blocked_channels", "blocked_guilds", "blocked_users")

    POST_URL = "commands/{id}"
    PRIMARY_KEY = "name"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop("id", None)
        self.name = kwargs.pop("name", None)
        self.documentation = kwargs.pop("documentation", None)
        self.cog = kwargs.pop("cog", None)
        self.aliases = kwargs.pop("aliases", "")
        self.blocked_channels = parse_command_channels(kwargs.pop("blocked_channels", []))
        self.blocked_guilds = parse_command_channels(kwargs.pop("blocked_guilds", []))
        self.blocked_users = parse_command_channels(kwargs.pop("blocked_users", []))
        self._dto = dto


class Task(API):
    __slots__ = ("id", "author", "created", "finished", "content", "number")

    POST_URL = "users/{author}/tasks/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.author = kwargs.pop('discord_id', None)
        self.created = parse_date(kwargs.pop('created', None))
        self.finished = parse_date(kwargs.pop('finished', None))
        self.content = kwargs.pop('content', None)
        self.number = kwargs.pop('number', None)
        self._dto = dto


class User(API):
    __slots__ = ("id", "league", "pubg", "osu", "location", "blocked")

    POST_URL = "users/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)  # type: int
        self.league = kwargs.pop('league', None)  # type: str
        self.pubg = kwargs.pop("pubg", None)  # type: str
        self.osu = kwargs.pop("osu", None)  # type: str
        self.location = kwargs.pop('location', None)  # type: str
        self.blocked = kwargs.pop("blocked", False)
        self._dto = dto

    def __str__(self):
        return str(self.id)

    async def add_reminder(self, create=True, **kwargs) -> typing.Optional[Reminder]:
        reminder = Reminder(self._dto, user=self.id, **kwargs)
        delta = (reminder.delta - datetime.datetime.utcnow()).total_seconds()
        if create and delta > 300:
            await reminder.save()
            self._dto._reminders[self.id] = {reminder.id: reminder}
        else:
            self.bot.loop.create_task(reminder.start())
        return reminder

    async def short_timer_optimisation(self, seconds, timer):
        await asyncio.sleep(seconds)
        self.bot.dispatch(timer.event, timer)

    async def add_task(self, create: bool = True, **kwargs):
        task_data = Task(self._dto, **kwargs)
        if create:
            await task_data.save()
        return task_data

    async def finish_task(self, tid):
        task = await self.get(Task, id=tid)
        if task:
            task.finished = datetime.datetime.utcnow()
            await task.update()
            return task

    async def delete_task(self, tid):
        response = await self.delete(f"users/{self.id}/tasks/{tid}")
        return response


class Tag(API):
    __slots__ = (
        "id", "author", "title", "content", "created", "edited", "orphaned", "previous_author", "guild", "count")

    POST_URL = "guilds/{guild}/tags/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.author = kwargs.pop('discord_id', kwargs.pop("author", None))
        self.title = kwargs.pop('title', None)
        self.content = kwargs.pop('content', None)
        self.created = parse_date(kwargs.pop("created", None))
        self.edited = parse_date(kwargs.pop("edited", None))
        self.orphaned = kwargs.pop("orphaned", None)
        self.previous_author = kwargs.pop("previous_author", None)
        self.guild = kwargs.pop('guild', None)
        self.count = kwargs.pop('count', 0)
        self._dto = dto

    def __str__(self):
        return self.content

    def __eq__(self, other):
        return self.title == other


class Channel(API):
    __slots__ = ("channel", "guild", "created", "blocker", "reason")

    POST_URL = "guilds/{guild}/channels/{id}"
    PRIMARY_KEY = "channel"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.channel = kwargs.pop("channel", None)
        self.guild = kwargs.pop("guild", None)
        self.created = parse_date(kwargs.pop("created", None))
        self.blocker = kwargs.pop('discord_id', kwargs.pop("blocker", None))
        self.reason = kwargs.pop("reason", None)
        self._dto = dto


class Alias(API):
    __slots__ = ("id", "original", "author", "created", "title", "guild", "count")

    POST_URL = "guilds/{guild}/aliases/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.original = kwargs.pop("original", None)
        self.author = kwargs.pop('discord_id', kwargs.pop("author", None))
        self.created = parse_date(kwargs.pop("created", None))
        self.title = kwargs.pop("title", None)
        self.guild = kwargs.pop('guild', None)
        self.count = kwargs.pop('count', 0)
        self._dto = dto

    def __str__(self):
        return self.title


class NickName(API):
    __slots__ = ("id", "member", "nickname", "changed", "guild")

    POST_URL = "guilds/{guild}/members/{member}/nicknames/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop("id", None)
        self.member = kwargs.pop('discord_id', kwargs.pop("member", None))
        self.nickname = kwargs.pop("nickname", None)
        self.changed = parse_date(kwargs.pop("changed", None))
        self.guild = kwargs.pop("guild", None)
        self._dto = dto

    def __str__(self):
        return self.nickname


class Member(API):
    __slots__ = ("id",
                 "user", "guild", "administrator", "last_spoke", "level", "achievement_points", "achievements",
                 "wallet",
                 "reputation", "experience", "_discord_id", "_userobj")

    POST_URL = "guilds/{guild}/members/{discord_id}"

    def __init__(self, dto: DiscordDto, userobj=None, **kwargs):
        self.id = kwargs.pop("id", None)
        self.guild = kwargs.pop('guild', None)
        self.administrator = kwargs.pop('administrator', None)
        self.last_spoke = parse_date(kwargs.pop('last_spoke', None))
        self.level = kwargs.pop('level', None)
        self.achievement_points = kwargs.pop('achievement_points', None)
        self.achievements = kwargs.pop("achievements", [])
        self.wallet = kwargs.pop('wallet', 0)
        self.reputation = kwargs.pop('reputation', None)
        self.experience = kwargs.pop("experience", None)
        self._discord_id = kwargs.pop("discord_id", None)
        self._dto = dto
        if isinstance(kwargs.get("user"), dict):
            self._userobj: User = userobj or User(dto, **kwargs.pop("user", {}))
        else:
            self._userobj = User(dto)

    def __getattr__(self, item):
        return getattr(self._userobj, item)

    @property
    def user_id(self):
        return self._userobj.id

    @property
    def league(self):
        return self._userobj.league

    @league.setter
    def league(self, value):
        self._userobj.league = value

    @property
    def pubg(self):
        return self._userobj.pubg

    @pubg.setter
    def pubg(self, value):
        self._userobj.pubg = value

    @property
    def osu(self):
        return self._userobj.osu

    @osu.setter
    def osu(self, value):
        self._userobj.osu = value

    @property
    def location(self):
        return self._userobj.location

    @location.setter
    def location(self, value):
        self._userobj.location = value

    async def save_user(self):
        await self._userobj.save()

    async def add_nickname(self, nickname) -> NickName:
        new_nickname = NickName(self._dto, member=self.user, nickname=nickname, guild=self.guild)
        response = await new_nickname.save()
        if response:
            return new_nickname

    async def get_nicknames(self) -> typing.List[NickName]:
        payload = await self.fetch_data(f"guilds/{self.guild}/members/{self.id}/nicknames")
        return [NickName(self._dto, **nickname) for nickname in payload]


class Prefix(API):
    __slots__ = ("id", "guild", "prefix", "author", "uses", "created")

    POST_URL = "guilds/{guild}/prefixes/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.guild = kwargs.pop('guild', None)
        self.prefix = kwargs.pop('prefix', None)
        self.author = kwargs.pop('discord_id', kwargs.pop("author", None))
        self.uses = kwargs.pop("uses", 0)
        self.created = parse_date(kwargs.pop('created', None))
        self._dto = dto

    def __str__(self):
        return self.prefix

    def __eq__(self, other):
        if hasattr(other, 'prefix'):
            return self.prefix == other.prefix
        else:
            return self.prefix == other


class Call(API):
    __slots__ = ("id", "tag", "alias", "author", "channel", "guild", "called")
    POST_URL = "calls/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.tag = kwargs.pop('tag', None)
        self.alias = kwargs.pop('alias', None)
        self.author = kwargs.pop('discord_id', kwargs.pop("author", None))
        self.channel = kwargs.pop('channel', None)
        self.guild = kwargs.pop('guild', None)
        self.called = parse_date(kwargs.pop('called', None))
        self._dto = dto


class Activity(API):
    __slots__ = ("id", "guild", "status", "role")
    POST_URL = "guilds/{guild}/activities/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop('id', None)
        self.guild = kwargs.pop('guild', None)
        self.status = kwargs.pop('status', None)
        self.role = kwargs.pop('role', None)
        self._dto = dto

    def get_role(self):
        return discord.utils.get(self.bot.get_guild(self.guild).roles, id=self.role)


class FAQ(API):
    __slots__ = ("id", "guild", "author", "uses", "question", "answer", "created_at")

    POST_URL = "guilds/{guild}/faq/{id}"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.id = kwargs.pop("id", None)
        self.guild = kwargs.pop("guild", None)
        self.author = kwargs.pop('discord_id', kwargs.pop("author", None))
        self.uses = kwargs.pop("uses", 0)
        self.question = kwargs.pop("question", "")
        self.answer = kwargs.pop("answer", "")
        self.created_at = parse_date(kwargs.pop("created_at", datetime.datetime.utcnow().replace(tzinfo=None)))
        self._dto = dto

    def __str__(self):
        return self.question

    async def call(self, ctx) -> str:
        embed = discord.Embed(title=self.question, timestamp=self.created,
                              description=self.answer)
        faq_author = ctx.guild.get_member(self.author)
        if faq_author:
            embed.set_author(name=faq_author.display_name, icon_url=faq_author.avatar_url)
        self.uses += 1
        await self.update()
        return await ctx.send(embed=embed)

    @property
    def created(self):
        return parse_date(self.created_at)


class Guild(API):
    __slots__ = (
        "guild", "premium", "tracking", "welcome_channel", "leaving_channel", "welcome_message", "leaving_message",
        "role", "delay", "_dto")
    POST_URL = "guilds/{guild}"
    PRIMARY_KEY = "guild"

    def __init__(self, dto: DiscordDto, **kwargs):
        self.guild: int = kwargs.pop('guild', None)
        self.premium: bool = kwargs.pop('premium', None)
        self.tracking: bool = kwargs.pop('tracking', None)
        self.welcome_channel: int = kwargs.pop("welcome_channel", None)
        self.leaving_channel: int = kwargs.pop("leaving_channel", None)
        self.welcome_message: str = kwargs.pop('welcome_message', None)
        self.leaving_message: str = kwargs.pop("leaving_message", None)
        self.available: bool = kwargs.pop("available", True)
        self.role: int = kwargs.pop('role', None)
        self.delay: int = kwargs.pop('delay', None)
        self._dto: DiscordDto = dto
        self._prefixes: typing.Dict[str, Prefix] = {data['prefix']: Prefix(self._dto, guild=self.guild, **data) for data
                                                    in
                                                    kwargs.pop("prefixes", {})}
        self._tags: typing.Dict[str, Tag] = {data['title']: Tag(self._dto, **data) for data in kwargs.pop("tags", {})}
        self._aliases: typing.Dict[str, Alias] = {data['title']: Alias(self._dto, **data) for data in
                                                  kwargs.pop("aliases", {})}
        self._activities: typing.Dict[str, Activity] = {data['status']: Activity(self._dto, **data)
                                                        for data in kwargs.pop("activities", {})}
        self._blocked_channels: typing.Dict[int, Channel] = {data['channel']: Channel(self._dto, **data) for data in
                                                             kwargs.pop("channels", {})}
        self._faqs: typing.Dict[str, FAQ] = {data['question']: FAQ(self._dto, **data) for data in
                                             kwargs.pop("faqs", {})}

    @property
    def blocked_channels(self):
        return self._blocked_channels

    @blocked_channels.setter
    def blocked_channels(self, value):
        self._blocked_channels = value

    @property
    def activities(self):
        return self._activities

    @activities.setter
    def activities(self, value):
        self._activities = value

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        self._tags = value

    @property
    def aliases(self):
        return self._aliases

    @aliases.setter
    def aliases(self, value):
        self._aliases = value

    @property
    def prefixes(self) -> typing.Dict[str, Prefix]:
        return self._prefixes

    @prefixes.setter
    def prefixes(self, value):
        self._prefixes = value

    @property
    def faqs(self):
        return self._faqs

    @faqs.setter
    def faqs(self, value):
        self._faqs = value

    @property
    def activity_roles(self) -> typing.List[discord.Role]:
        return [activity.get_role() for activity in self._activities.values()]

    async def get_member(self, pid: int) -> Member:
        member: Member = await self.get(Member, guild=self.guild, user=pid, create=True)
        if member:
            user = await self.get(User, id=pid)
            member._userobj = user
        return member

    async def delete_member(self, pid: int) -> typing.Optional[bool]:
        response = await self.delete(f"{self.base_url}guilds/{self.guild}/members/{pid}")
        return response

    async def add_member(self, pid: int) -> typing.Optional[Member]:
        member = Member(self._dto, user=pid, guild=self.guild)
        await member.save()
        return member

    def find_tag_by_id(self, id) -> typing.Optional[Tag]:
        for tag in self.tags.values():
            if tag.id == id:
                return tag

    def get_tag(self, tag: str, pop=False) -> typing.Tuple[Tag, typing.Union[Alias, None]]:
        if pop:
            response = self._tags.pop(tag, self._aliases.pop(tag, None))
        else:
            response = self._tags.get(tag, self._aliases.get(tag))
        if isinstance(response, Alias):
            return self.find_tag_by_id(response.original), response
        elif response:
            return response, None
        else:
            raise TagNotFound(tag)

    async def get_member_tags(self, author: int) -> typing.List[Tag]:
        member = await self.get_member(author)
        return [tag.title for tag in self.tags.values() if tag.author == member.id]

    def get_all_aliases(self, tag: str) -> typing.List[Alias]:
        payload = []
        for alias in self.aliases:
            if alias == tag:
                payload.append(alias)
        payload = [self.aliases.pop(alias, None) for alias in payload]
        return payload

    async def create_tag(self, content: str, title: str, author: int) -> typing.Optional[Tag]:
        try:
            self.get_tag(title)
            raise TagAlreadyExists(title)
        except TagNotFound:
            new_tag = await self.get(Tag, {"content": content, "title": title, "author": author}, create=True,
                                     guild=self.guild)
            if new_tag:
                self.tags[title] = new_tag
            return new_tag

    async def create_alias(self, original, new_alias, author):
        tag, alias = self.get_tag(original)
        if tag and not alias:
            nalias = Alias(self._dto, original=tag.id, author=author, title=new_alias,
                           guild=self.guild)
            response = await nalias.save()
            if response:
                self.aliases[new_alias] = nalias
            return nalias
        else:
            raise TagAlreadyExists(new_alias)

    async def delete_alias(self, alias):
        selected = self.get_alias(alias.title, pop=True)
        if selected:
            response = await selected.delete()
            if response:
                return selected

    async def edit_tag(self, title, new_content):
        tag, alias = self.get_tag(title)
        if tag is not None:
            tag.edited = datetime.datetime.utcnow()
            tag.content = new_content
            await tag.update()
            return tag

    async def delete_tag(self, tag: Tag) -> bool:
        tag = self.get_tag(tag.title, True)
        aliases = self.get_all_aliases(tag[0].title)
        for alias in aliases:
            await alias.delete()
        response = await tag[0].delete()
        return response

    def get_alias(self, alias: str, pop=False) -> typing.Union[Alias, None]:
        if not pop:
            data = self._aliases.get(alias)
        else:
            data = self._aliases.pop(alias, None)
        if data is None:
            raise TagNotFound(alias)
        else:
            return data

    async def create_prefix(self, prefix: str, author: int) -> typing.Optional[Prefix]:
        new_prefix = await self.get(Prefix, {"prefix": prefix, "author": author}, guild=self.guild, create=True)
        if new_prefix:
            self._prefixes[prefix] = new_prefix
            return new_prefix

    async def delete_prefix(self, prefix) -> typing.Optional[Prefix]:
        selected = self._prefixes.pop(prefix, None)
        if selected is not None:
            await selected.delete()
            return selected

    async def call_tag(self, ctx, request):
        tag, alias = self.get_tag(request)
        if alias:
            alias.count += 1
            await alias.update()
        else:
            tag.count += 1
            await tag.update()
        data = Call(self._dto, guild=ctx.guild.id, channel=ctx.channel.id, author=ctx.author.id,
                    tag=tag.id if hasattr(tag, "id") else None, alias=alias.id if hasattr(alias, "id") else None)
        await data.save()
        return tag, alias

    async def add_activity(self, name, role):
        new_activity = await self.get(Activity, {"status": name.lower()}, guild=self.guild)
        if not new_activity:
            new_activity = Activity(self._dto, guild=self.guild, status=name.lower(), role=role)
            await new_activity.save()
        return new_activity

    async def edit_activity(self, name, role, new_name=None):
        activity = await self.get(Activity, {"status": name}, guild=self.guild)
        if activity:
            activity.role = role
            if new_name:
                activity.status = new_name
        await activity.save()

    async def delete_activity(self, name):
        selected = self.activities.get(name, None)
        if selected:
            response = await selected.delete()
            if response:
                return self.activities.pop(name)

    async def block_channel(self, channel, author, reason=None):
        block = Channel(self._dto, channel=channel, author=author, reason=reason)
        response = await block.save()
        if response:
            self._blocked_channels[channel] = block
            return block

    async def unblock_channel(self, channel):
        block = self.blocked_channels.get(channel)
        if block is not None:
            response = await block.delete()
            if response:
                del self.blocked_channels[channel]
                return block

    async def add_faq(self, ctx, question: str, answer: str) -> typing.Optional[FAQ]:
        new_faq = FAQ(self._dto, guild=self.guild, author=ctx.author.id, question=question, answer=answer)
        response = await new_faq.save()
        if response:
            return new_faq

    async def get_faqs(self):
        self._faqs = await self.get_all(FAQ, guild=self.guild)

    async def edit_faq(self, question: str, new_answer: str) -> FAQ:
        target = await self.get(FAQ, post_data={"q": question}, guild=self.guild)
        if target is None:
            raise UserInputError(message="Question not found")
        else:
            target.answer = new_answer
            response = await target.update()
            if response:
                return target

    async def delete_faq(self, question: str) -> FAQ:
        target = await self.get(FAQ, post_data={"q": question}, guild=self.guild)
        if target is None:
            raise UserInputError(message="Question matching query not found")
        response = await target.delete()
        return response


if __name__ == '__main__':
    myobj = Tag
    print(myobj.POST_URL)
    try:
        print(myobj.POST_URL.format_map({"12": 1, "1212": 2}))
    except KeyError:
        print("uh oh!")
    # from Iceteabot import Iceteabot
    #
    #
    # async def myfunc():
    #     mydto = DiscordDto(Iceteabot(
    #         config=config))
    #     myguild = await mydto.get(Guild, guild=92730839854493696, create=True)
    #     my_member = await myguild.get_member(92730223316959232)
    #     await myguild.create_prefix("<<", 92730223316959232)
    #
    #
    # config = {"api_keys": {"iceteacity": "83e5829b9e4ab5c7f80f06cb98f364570ad669e5"},
    #           "base_url": "http://127.0.0.1:8000/api/"}
    # loop = asyncio.get_event_loop().run_until_complete(myfunc())
    # print(True)
