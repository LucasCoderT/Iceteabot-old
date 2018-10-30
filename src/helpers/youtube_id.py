import asyncio
from aiohttp import ClientSession, ClientResponseError
from bs4 import BeautifulSoup
import re
from lxml import html


async def grab_channel_feed(channel_url: str):
    async with ClientSession() as session:
        async with session.get(channel_url) as response:
            tree = html.fromstring(await response.text())
            channel_feed_url = tree.xpath("/html/head/link[14]")[0].attrib['href']
            return channel_feed_url


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(grab_channel_feed("https://www.youtube.com/USER/LoLChampSeries"))
