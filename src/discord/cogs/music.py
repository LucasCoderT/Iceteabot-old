import asyncio
import datetime
import os
import re
import typing
import ujson

import discord
import isodate
import youtube_dl
from bs4 import BeautifulSoup
from discord.ext import commands

from src.discord.utils.permissions import bot_administrator


class YoutubeAPI:
    def __init__(self, bot):
        self.bot = bot
        self.api_key = bot.config['api_keys']['google']

    async def get_result(self, search: str) -> str:
        async with self.bot.aioconnection.get(f"https://www.youtube.com/results?search_query={search}") as response:
            if response.status == 200:
                data = await response.read()
                soup = BeautifulSoup(data, 'lxml')
                videos = soup.find_all(attrs={'class': 'yt-lockup-title '})
                for video in videos:
                    myv = video.find('a')
                    link = myv['href']
                    if re.search(r'&list=', link):
                        continue
                    else:
                        return f"https://youtube.com{link}"

    async def get_length(self, video_id: str):
        details = await self.get_details(video_id)
        length = isodate.parse_duration(details['items'][0]['contentDetails']['duration'])
        return length

    async def search(self, query: str):
        encoded_query = {"part": "snippet", "q": query, "key": self.api_key}
        async with self.bot.aioconnection.get(
                f"https://www.googleapis.com/youtube/v3/search", params=encoded_query) as response:
            if response.status == 200:
                data = await response.json()
                return data

    async def get_details(self, video_id: str or list) -> list:
        async with self.bot.aioconnection.get(
                f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails%2Csnippet&id={video_id}&key={self.api_key}") as response:
            if response.status == 200:
                return await response.json()

    async def get_playlist_details(self, video_ids: list) -> list:
        videos = []
        n = max(1, 50)
        chunked_list = [video_ids[i:i + n] for i in range(0, len(video_ids), n)]
        for chunk in chunked_list:
            videos.append(await self.get_details(",".join(chunk)))
        return videos

    async def get_response(self, url) -> dict:
        async with self.bot.aioconnection.get(url) as response:
            if response.status == 200:
                return await response.json()

    async def get_play_list(self, url) -> list or None:
        playlist_id = re.search(r'\?list=(.*)', url).group(1)
        async with self.bot.aioconnection.get(
                f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails%2Csnippet&maxResults=50&playlistId={playlist_id}&key={self.api_key}") as response:
            if response.status == 200:
                videos = []
                data = await response.json()
                while True:
                    for video in data['items']:
                        video_url = "https://www.youtube.com/watch?v={}".format(video['contentDetails']['videoId'])
                        videos.append(video_url)
                    if 'nextPageToken' not in data:
                        break
                    data = await self.get_response(
                        f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails%2Csnippet&maxResults=50&pageToken={data['nextPageToken']}&playlistId={playlist_id}&key={self.api_key}")
                return videos


def get_time(length):
    return str(datetime.timedelta(seconds=int(length)))


class Song:
    def __init__(self, **kwargs):
        self.duration = kwargs.get('duration')
        self.start_time = None
        self.title = kwargs.get('title')
        self.thumbnail = kwargs.get('thumbnail')
        self.id = kwargs.get('id')
        self.url = kwargs.get('webpage_url')
        self.stream_url = kwargs.get('url')
        self.requester = kwargs.get('requester')
        self.uploader = kwargs.get('channelTitle') or kwargs.get('uploader')
        self.uploader_url = kwargs.get('uploader_url')


class VoiceState(discord.PCMVolumeTransformer):
    def __init__(self, bot, ctx, ):
        self.choosing = False
        self.results = []
        self.choosing_message = None
        self.current = None
        self.voice = None
        self.bot = bot
        self.repeating = False
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.audio_player = None  # type: asyncio.Task()
        self.ctx = ctx
        self.playlist_que = asyncio.Queue()
        self.playlist_processor_task = None
        self.finished_playing = False
        self.lock = None

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        if self.songs.empty():
            return False

    def done_playing(self):
        if self.songs.empty():
            return True

    def skip(self):
        if self.ctx.guild.voice_client.is_playing():
            self.ctx.guild.voice_client.stop()

    def toggle_next(self, error):
        if error is None:
            self.songs.task_done()
            self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self, ctx):
        while not self.finished_playing:
            self.play_next_song.clear()
            guild = self.bot.get_guild(ctx.guild.id)
            if len(guild.voice_client.channel.members) == 1:
                break
            try:
                if not self.repeating:
                    self.current = await asyncio.wait_for(fut=self.songs.get(), timeout=1, loop=self.bot.loop)
            except asyncio.TimeoutError:
                break

            self.original = discord.FFmpegPCMAudio(source=self.current.stream_url)
            if not self.repeating:
                await ctx.send(
                    f"Now playing:\n**{self.current.title} {get_time(self.current.duration)}**\n")
            if not self.finished_playing:
                self.current.start_time = datetime.datetime.now()
                # await guild_player.play(self.current.url)
                ctx.guild.voice_client.play(self.original, after=self.toggle_next)
                await self.play_next_song.wait()
        self.bot.dispatch("queue_finish", self)

    async def playlist_processor(self):
        num_processed = 0
        while True:
            with youtube_dl.YoutubeDL(self.bot.config['youtube_dl_options']) as ydl:
                try:
                    next_up = await asyncio.wait_for(fut=self.playlist_que.get(), timeout=5, loop=self.bot.loop)
                    self.playlist_que.task_done()
                except asyncio.TimeoutError:
                    break
                information = await self.bot.loop.run_in_executor(None, ydl.extract_info, next_up, False)
                if information is not None:
                    song = Song(**information, requester=self.ctx.author)
                    await asyncio.wait_for(self.songs.put(song), timeout=None,
                                           loop=self.bot.loop)
                    num_processed += 1
        return await self.ctx.send(f"Added {num_processed} Songs to the Queue")


class RadioStream(discord.PCMVolumeTransformer):
    def __init__(self, **kwargs):
        self.ctx = kwargs.get('ctx')
        self.author = kwargs.get('author')
        self.bot = kwargs.get('bot')
        self.finished = asyncio.Event()

        self.volume = 0.1
        self.original = kwargs.get('station')

    def toggle_next(self, error):
        if error is None:
            self.finished.set()
            self.bot.dispatch("queue_finish", self)

    async def play_station(self):
        self.ctx.guild.voice_client.play(self.original, after=self.toggle_next)
        await asyncio.Event.wait()


class Music:
    """Voice related commands.

    Works in multiple servers at once.
    """

    def __init__(self, bot):
        self.bot = bot
        self.youtube = YoutubeAPI(bot)
        self.youtube_dl_options = self.bot.config['youtube_dl_options']
        self.voice_states = {}
        try:
            with open(os.path.join('data', 'stations.json')) as file:
                self.stations = ujson.load(file)
        except:
            self.stations = None

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        guild_data = ctx.guild_data
        return guild_data.premium

    def __unload(self):
        for item in self.voice_states.values():
            item.playlist_processor_task.cancel()
            item.audio_player.cancel()
        del self.voice_states

    async def repeating_check(self, ctx):
        state = self.get_voice_state(ctx)
        return state.repeating

    def get_voice_state(self, ctx):
        state = self.voice_states.get(ctx.guild.id)
        if state is None:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    async def on_queue_finish(self, state: typing.Union[VoiceState, RadioStream]):
        if isinstance(state, VoiceState):
            if state.ctx.guild.voice_client is not None:
                state.audio_player.cancel()
                if state.lock is not None:
                    await state.lock.wait()
                    state.playlist_processor_task.cancel()
                await state.ctx.guild.voice_client.disconnect(force=True)
                await state.ctx.send("Queue Complete")
                del self.voice_states[state.ctx.guild.id]
        else:
            await state.ctx.guild.voice_client.disconnect(force=True)
            await state.ctx.send("Queue Complete")
            del self.voice_states[state.ctx.guild.id]

    @commands.command()
    async def join(self, ctx, target_channel: discord.VoiceChannel = None):
        """Joins a voice channel."""
        if ctx.guild.voice_client is None:
            if target_channel is None:
                self.get_voice_state(ctx)
                await ctx.author.voice.channel.connect()
            else:
                await target_channel.connect()

    @commands.command()
    async def leave(self, ctx):
        """Leaves the current voice channel"""
        if ctx.guild.voice_client is not None:
            await ctx.guild.voice_client.disconnect(force=True)
            del self.voice_states[ctx.guild.id]

    @commands.command(hidden=True)
    @commands.check(bot_administrator)
    async def vmove(self, ctx, target_channel: discord.VoiceChannel = None):
        """Moves the bot to another voice channel"""
        if ctx.guild.voice_client is not None:
            if not target_channel:
                await ctx.guild.voice_client.move_to(ctx.author.voice.channel)
            else:
                await ctx.guild.voice_client.move_to(target_channel)

    async def yt_add_to_que(self, ctx, url):
        voice_state = self.get_voice_state(ctx)
        if "playlist" in url:
            songs = await self.youtube.get_play_list(url)
            if len(songs) > 5:
                first_song = songs.pop(0)
                await self.yt_add_to_que(ctx, first_song)
                for song in songs:
                    await voice_state.playlist_que.put(song)
                voice_state.playlist_processor_task = self.bot.loop.create_task(voice_state.playlist_processor())

                return
        with youtube_dl.YoutubeDL(self.youtube_dl_options) as ydl:
            information = await self.bot.loop.run_in_executor(None, ydl.extract_info, url, False)
        if information is None:
            return await ctx.send("Unable to process this song")
        else:
            if "entries" in information:
                if len(information['entries']) > 5:
                    first_song = information['entries'].pop(0)
                    song = Song(**first_song, requester=ctx.author)
                    await asyncio.wait_for(voice_state.songs.put(song), timeout=None, loop=self.bot.loop)
                    for entry in information['entries']:
                        await voice_state.playlist_que.put(entry)
                    voice_state.playlist_processor_task = self.bot.loop.create_task(voice_state.playlist_processor())
                    return
                for entry in information['entries']:
                    song = Song(**entry, requester=ctx.author)
                    await asyncio.wait_for(voice_state.songs.put(song), timeout=None, loop=self.bot.loop)
                if len(information['entries']) > 5:
                    return await ctx.send(f"Added {len(information['entries'])} Songs to the Queue")
                else:
                    await ctx.send(f"\n".join([f"Added:\n**{song.title} {get_time(song.duration)}**\n<{song.url}>\n"
                                               f"requested by _{song.requester}_" for song in
                                               voice_state.songs._queue[:5]]))
            else:
                song = Song(**information, requester=ctx.author)
                await asyncio.wait_for(voice_state.songs.put(song), timeout=None, loop=self.bot.loop)
                await ctx.send(f"Added:\n**{song.title} {get_time(song.duration)}**\n<{song.url}>\n"
                               f"requested by _{song.requester}_")
                return song
        return

    async def top_search_results(self, ctx, query):
        search_results = await self.youtube.search(query)
        voice_state = self.get_voice_state(ctx)
        results = []
        counter = 1
        if search_results is not None:
            embed = discord.Embed(title=f"Search results",
                                  description=f"To choose, use ``{ctx.prefix}choose <number>``\n"
                                              f"Example: ``{ctx.prefix}choose 2`` would pick the second option.")
            for result in search_results['items']:
                if result['id']['kind'] == "youtube#playlist":
                    continue
                else:
                    results.append(f"https://www.youtube.com/watch?v={result['id']['videoId']}")
                    duration = await self.youtube.get_length(result['id']['videoId'])
                    title = result['snippet']['title']
                    uploader = result['snippet']['channelTitle']
                    embed.add_field(name=f"Result {counter}", value=f"{duration} - **{title}** by **{uploader}**")
                    counter += 1
            voice_state.choosing_message = await ctx.send(embed=embed)
            voice_state.choosing = True
            voice_state.results = results
            await asyncio.sleep(600)
            try:
                voice_state = self.voice_states[ctx.guild.id]
            except KeyError:
                return
            if voice_state is not None:
                if voice_state.choosing_message is not None:
                    try:
                        await ctx.channel.get_message(voice_state.choosing_message.id)
                    except discord.NotFound:
                        return
                if voice_state.choosing:
                    voice_state.choosing = False
                    voice_state.results = []
                    await ctx.send("Times up, no response given")
                    try:
                        await ctx.message.delete()
                    except discord.Forbidden:
                        pass
                    await voice_state.choosing_message.delete()
                    voice_state.choosing_message = None
        else:
            return await ctx.send("Nothing found")

    @commands.command(name="choose")
    async def choose(self, ctx, number: int):
        """Chooses a song to play from the list of search results, must first use the play command"""
        voice_state = self.get_voice_state(ctx)
        if voice_state is not None:
            if voice_state.choosing:
                try:
                    url = voice_state.results[number - 1]
                except IndexError:
                    return await ctx.send(f"Invalid choice, choose a number between 1-{len(voice_state.results)}")
                song = await asyncio.wait_for(self.yt_add_to_que(ctx, url), timeout=None, loop=self.bot.loop)
                await ctx.send(
                    f"Added:\n**{song.title} {get_time(song.duration)}**\n<{song.url}>\n"
                    f"requested by _{song.requester}_ \n")

                if voice_state.voice is None:
                    await ctx.invoke(self.join)
                    if ctx.guild.voice_client is None:
                        return
                if voice_state.audio_player is None:
                    voice_state.audio_player = self.bot.loop.create_task(voice_state.audio_player_task(ctx))
                voice_state.choosing = False
                voice_state.results = []
                try:
                    await ctx.message.delete()
                except discord.Forbidden:
                    pass
                await voice_state.choosing_message.delete()
                voice_state.choosing_message = None
            else:
                await ctx.send(f"There's no selection active in this guild - are you sure you ran "
                               f"``{ctx.prefix}play?``\n\n"
                               f"To play a song...\n"
                               f"* Join a voice channel\n"
                               f"* Use ``{ctx.prefix}play <song name/link>``\n"
                               f"* Choose one of the song options with {ctx.prefix}choose <song number>")

    @commands.command()
    async def play(self, ctx, *, data: str):
        """Plays a song.

        If there is a song currently in the queue, then it is
        queued until the next song is done playing.

        This command automatically searches from YouTube.
        The list of supported sites can be found here:
        https://rg3.github.io/youtube-dl/supportedsites.html
        """
        if ctx.author.voice is None:
            await ctx.send("you need to be in the voice channel to request songs")
            return
        state = self.get_voice_state(ctx)
        if state.repeating:
            return await ctx.send("I am currently repeating a song, use the ``stop`` command to cancel this")
        if data is None:
            raise commands.MissingRequiredArgument
        else:
            if re.search(r"^(https?\:\/\/)(www\.|m\.)?", data):
                await asyncio.wait_for(self.yt_add_to_que(ctx, data), timeout=None, loop=self.bot.loop)
            else:
                return await self.top_search_results(ctx, data)
        if state.voice is None:
            await ctx.invoke(self.join)
            if ctx.guild.voice_client is None:
                return
        if state.audio_player is None:
            state.audio_player = self.bot.loop.create_task(state.audio_player_task(ctx))

    @commands.command()
    @commands.guild_only()
    async def volume(self, ctx, value: int):
        """Sets the volume of the bot. Default Volume is 10%"""
        if ctx.author.voice is None:
            await ctx.send("you need to be in the voice channel to request songs")
            return
        if ctx.guild.voice_client is not None:
            new_volume = float(value / 100)
            state = self.get_voice_state(ctx)
            if ctx.guild.voice_client.is_playing():
                state.volume = new_volume
                await ctx.send('Set the volume to {:.0%}'.format(state.volume))

    @commands.command()
    async def pause(self, ctx):
        """Pauses the song."""
        if ctx.author.voice is None:
            await ctx.send("you need to be in the voice channel")
            return
        if ctx.guild.voice_client is not None:
            if ctx.guild.voice_client.is_playing():
                ctx.guild.voice_client.pause()

    @commands.command()
    async def resume(self, ctx):
        """Resumes the song."""
        if ctx.author.voice is None:
            await ctx.send("you need to be in the voice channel")
            return
        if ctx.guild.voice_client is not None:
            if ctx.guild.voice_client.is_paused():
                ctx.guild.voice_client.resume()

    @commands.command()
    async def stop(self, ctx):
        """leaves the voice channel. This also clears the queue.
        """
        if ctx.author.voice.channel.id != ctx.guild.voice_client.channel.id:
            await ctx.send("you need to be in the voice channel")
            return
        if ctx.guild.voice_client is not None:
            state = self.get_voice_state(ctx)
            if ctx.guild.voice_client.is_playing():
                ctx.guild.voice_client.stop()
                self.bot.dispatch("queue_finish", state)

    @commands.command()
    async def skip(self, ctx):
        """Skips the currently playing song"""
        if ctx.author.voice is None:
            await ctx.send("you need to be in the voice channel")
            return
        state = self.get_voice_state(ctx)
        if hasattr(ctx.guild.voice_client, 'is_playing') is False:
            await ctx.send('Not playing any music right now...')
            return
        else:
            if not state.repeating:
                state.skip()

    @commands.command(aliases=['np'])
    async def nowplaying(self, ctx):
        """Displays information about the song currently playing"""
        if ctx.guild.voice_client is not None:
            if ctx.guild.voice_client.is_playing():
                current_song = self.get_voice_state(ctx).current
                embed = discord.Embed(title=current_song.title, description=f"Uploaded by {current_song.uploader}")
                current_time = datetime.datetime.now()
                embed.url = current_song.url
                embed.set_thumbnail(url=current_song.thumbnail)
                embed.add_field(name="Time Left:",
                                value=f"{get_time(current_song.duration - ((current_time - current_song.start_time).total_seconds()))}")
                embed.timestamp = current_time
                embed.set_footer(text=f"Requested by {current_song.requester}",
                                 icon_url=current_song.requester.avatar_url)
                await ctx.send(embed=embed)
        else:
            await ctx.send("Not currently playing any song")

    @commands.command(aliases=['repeat'])
    async def repeatlast(self, ctx):
        """Repeats the currently playing song"""
        if ctx.guild.voice_client is not None:
            if ctx.author.voice is None:
                await ctx.send("you need to be in the voice channel")
                return
            if ctx.guild.voice_client.is_playing():
                state = self.get_voice_state(ctx)
                if not state.repeating:
                    await state.songs.put(state.current)
                    await ctx.send("\N{OK HAND SIGN}")

    @commands.command()
    async def repeatforever(self, ctx):
        """Repeats the currently playing song forever, ``music stop`` to end repeat"""
        if ctx.author.voice.channel.id != ctx.guild.voice_client.channel.id:
            await ctx.send("you need to be in the voice channel")
            return
        if ctx.guild.voice_client is not None:
            if ctx.guild.voice_client.is_playing():
                state = self.get_voice_state(ctx)
                state.repeating = True
                await ctx.send(f"Now repeating **{state.current.title}**, use the ``stop`` command to cancel")

    @commands.command()
    async def queue(self, ctx):
        """Displays all the items in the current queue"""
        if ctx.guild.voice_client is not None:
            state = self.get_voice_state(ctx)
            if state.songs.qsize() == 0:
                await ctx.send("No items in queue")
                return
            total_length = 0
            msg = "**Current Queue** (_{0}_)\n"
            counter = 0
            for song in state.songs._queue:
                if counter > 10:
                    msg += f"and **{state.songs.qsize() - 10}** more"
                    break
                total_length += int(song.duration)
                msg += f"\t[**{counter}**]: _{song.title}_ requested by _{song.requester}_\n"
                counter += 1
            await ctx.send(msg.format(get_time(total_length)))
        else:
            await ctx.send("No items in Queue")

    @commands.command(hidden=True)
    async def radio(self, ctx, *, station: str):
        if station in self.stations:
            self.voice_states[ctx.guild.id] = RadioStream(
                station=station,
                author=ctx.author,
                bot=ctx.bot,
                ctx=ctx
            )


def setup(bot):
    bot.add_cog(Music(bot))
