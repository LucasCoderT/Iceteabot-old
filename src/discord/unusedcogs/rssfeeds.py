import datetime
from time import mktime

import discord
from bs4 import BeautifulSoup
from discord.ext import commands



class Subscriptions:
    def __init__(self, bot):
        self.bot = bot

    def __str__(self):
        return self.__class__.__name__

    def __unload(self):
        for task in self.bot.subscriptions.values():
            task._task.cancel()
        self.bot.subscriptions = {}

    async def on_subscription_update(self, feed_data, rss):
        newest_entry = feed_data['entries'][0]
        try:
            thumbnail = newest_entry['media_thumbnail'][0]['url']
        except:
            thumbnail = None
        embed = discord.Embed(title=f"New post {newest_entry['title']}")
        cleaned_data = BeautifulSoup(newest_entry['summary'], "lxml").find('div').get_text()
        if cleaned_data is not None:
            embed.add_field(name='New Content', value=f"{cleaned_data[:200]}...")
        embed.add_field(name="Url", value=newest_entry['feedburner_origlink'])
        embed.set_thumbnail(url=thumbnail)
        embed.timestamp = datetime.datetime.fromtimestamp(mktime(newest_entry['published_parsed']))
        for channel in rss.channels.keys():
            if rss.should_post(newest_entry, channel):
                d_channel = self.bot.get_channel(int(channel))
                if d_channel is not None:
                    try:
                        message = await d_channel.send(embed=embed)
                    except discord.Forbidden:
                        continue
                else:
                    continue
                rss.new_post(message, newest_entry)
                await rss.save()


    @commands.command(name="activesubs")
    @commands.is_owner()
    async def active_subs(self, ctx):
        await ctx.send(f"This channel is subscribed to {len(list(ctx.channel_subscriptions))} feeds")


def setup(bot):
    bot.add_cog(Subscriptions(bot))
