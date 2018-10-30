import asyncio
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
import youtube_dl
import re
from src.discord.utils import permissions
import os
from src.google.youtube import get_result, get_play_list
import datetime

try:
    if not discord.opus.is_loaded():
        discord.opus.load_opus('libopus-0.dll')
except OSError:  # Incorrect bitness
    opus = False
except:  # Missing opus
    opus = None
else:
    opus = True

youtube_dl_options = {
    'source_address': '0.0.0.0',
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': "mp3",
    'outtmpl': '%(id)s',
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'outtmpl': "data/music/%(id)s.%(ext)s",
    'default_search': 'auto',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}


class Que:
    def __init__(self):
        self.que = []
        self.current_song: None
        self.volume = 1.0
        self.files = []


class Song:
    def __init__(self, **kwargs):
        self.file = f"data/music/{kwargs['id']}.mp3"
        self.length = kwargs.get('duration')
        self.title = kwargs.get('title')
        self.thumbnail = kwargs.get('thumbnail')
        self.id = kwargs.get('id')
        self.url = kwargs.get('webpage_url')


class Voice:
    def __init__(self, bot):
        self.bot = bot
        self.ques = {}

    @commands.command()
    @commands.check(permissions.bot_administrator)
    async def join(self, ctx):
        if ctx.author.voice is not None and ctx.server.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.command()
    async def leave(self, ctx):
        if ctx.server.voice_client is not None:
            del self.ques[ctx.server.id]
            await ctx.server.voice_client.disconnect()

    @staticmethod
    async def am_connected(ctx):
        # Checks if neither author nor bot is in a Voice channel
        if ctx.server.voice_client is None and ctx.author.voice is None:
            return False
        # Checks if the author is in a channel but not the bot
        elif ctx.author.voice is not None and ctx.server.voice_client is None:
            return True
        # Checks if the bot is in a channel and the author is in a channel
        elif ctx.author.voice is not None and ctx.server.voice_client is None:
            return True

    async def play_list_extractor(self, ctx, url):
        songs = await get_play_list(url)
        msg = []
        await ctx.send(f"playlist contains {len(songs)} songs. Please wait till I finished loading...")
        await ctx.trigger_typing()
        for song in songs:
            with youtube_dl.YoutubeDL(youtube_dl_options) as ydl:
                information = await asyncio.get_event_loop().run_in_executor(None, ydl.extract_info, song, False)
            if information is None:
                continue
            song = Song(**information)
            self.ques[ctx.server.id].que.append(song)
            msg.append(
                f"Added:\n**{song.title} {self.get_time(song.length)}**\n<{song.url}>\nrequested by _{ctx.author.display_name}_ \n")
        if len("".join(msg)) > 2000:
            await ctx.send(f"added {len(songs)} songs to the que, too many to display")
        else:
            await ctx.send("".join(msg))

    async def yt_add_to_que(self, ctx, url):
        with youtube_dl.YoutubeDL(youtube_dl_options) as ydl:
            information = await asyncio.get_event_loop().run_in_executor(None, ydl.extract_info, url, False)
            song = Song(**information)
            self.ques[ctx.server.id].que.append(song)


    @staticmethod
    def get_time(length):
        return str(datetime.timedelta(seconds=int(length)))

    async def _play_que(self, ctx):
        while len(self.ques[ctx.server.id].que) != 0 and ctx.server.voice_client is not None:
            if len(ctx.server.voice_client.channel.members) <= 1:
                for song in self.ques[ctx.server.id].files:
                    os.remove(song)
                del self.ques[ctx.server.id]
                await ctx.server.voice_client.disconnect()
                return
            song = self.ques[ctx.server.id].que[0]
            self.ques[ctx.server.id].files.append(song.file)
            if os.path.isfile(song.file):
                pass
            else:
                with youtube_dl.YoutubeDL(youtube_dl_options) as ydl:
                    await asyncio.get_event_loop().run_in_executor(None, ydl.download, [song.url])
            await ctx.send(
                f"Now playing:\n**{song.title} {self.get_time(song.length)}**\n<{song.url}>\nrequested by _{ctx.author.display_name}_ \n")

            music = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(source=song.file), volume=self.ques[ctx.server.id].volume)
            ctx.server.voice_client.play(music)
            await asyncio.sleep(int(song.length))
            try:
                if song.id == self.ques[ctx.server.id].que[0].id:
                    del self.ques[ctx.server.id].que[0]
            except:
                return

        if len(self.ques[ctx.server.id].que) == 0:
            await ctx.send("Queue completed")
            await ctx.server.voice_client.disconnect()
            for song in self.ques[ctx.server.id].files:
                os.remove(song)
            del self.ques[ctx.server.id]

    @commands.command()
    @commands.cooldown(30, 5, BucketType.guild)
    async def play(self, ctx, *, data: str = None):
        if ctx.me.voice is None and ctx.author.voice is None:
            await ctx.send("You need to be in a channel for me to join")
            return
        if self.ques.get(ctx.server.id) is None:
            self.ques[ctx.server.id] = Que()
        if data is None:
            raise commands.MissingRequiredArgument
        elif re.search(r'^(https?\:\/\/)?(www\.|m\.)?(youtube\.com|youtu\.?be)\/.+$', data):
            if re.search(r'^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)'
                         r'(\/playlist\?).*(list=)(.*)(&|$)', data):
                await self.play_list_extractor(ctx, data)
            else:
                await self.yt_add_to_que(ctx, data)
        elif re.search(r'^(https?\:\/\/)?(www\.)?(soundcloud\.com\/)', data):
            await self.yt_add_to_que(ctx, data)
        else:
            search = await get_result(data)
            if re.search(r'&list=', search):
                await ctx.send("found a playlist, loading now")
                await self.play_list_extractor(ctx, search)
            elif re.search(r'&list=', search) is None:
                await self.yt_add_to_que(ctx, search)
            else:
                await ctx.send("Search returned no results")
        if bool(ctx.me.voice) is False and bool(ctx.author.voice):
            await ctx.author.voice.channel.connect()
        try:
            if ctx.server.voice_client.is_playing() is False:
                await self._play_que(ctx)
        except AttributeError:
            await ctx.author.voice.channel.connect()

    @commands.command()
    @commands.cooldown(10, 1, BucketType.guild)
    async def volume(self, ctx, volume: int):
        new_volume = float(volume / 100)
        if ctx.server.voice_client is None:
            await ctx.send("I'm not in a voice channel :cry:")
        else:
            self.ques[ctx.server.id].volume = new_volume
            ctx.server.voice_client.source.volume = new_volume
            await ctx.send(f"Set volume to {new_volume}% ")

    @commands.command()
    @commands.cooldown(10, 1, BucketType.guild)
    async def skip(self, ctx):
        if hasattr(ctx.server.voice_client, 'is_playing'):
            ctx.server.voice_client.stop()
            await ctx.send(f"**{ctx.author.display_name}** has Skipped **{self.ques[ctx._guild_id.id].que[0].title}**")
            del self.ques[ctx.server.id].que[0]
            await self._play_que(ctx)
        else:
            await ctx.send("I'm not currently playing anything")

    @commands.command()
    async def shuffle(self, ctx):
        pass

    @commands.command()
    async def pause(self, ctx):
        if hasattr(ctx.server.voice_client, 'is_playing'):
            ctx.server.voice_client.pause()

    @commands.command()
    async def resume(self, ctx):
        if hasattr(ctx.server.voice_client, 'is_playing') and ctx.server.voice_client.is_paused():
            ctx.server.voice_client.resume()


def setup(bot):
    bot.add_cog(Voice(bot))
