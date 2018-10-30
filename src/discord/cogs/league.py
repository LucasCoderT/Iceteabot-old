import asyncio
import datetime

import discord
import league
import timeago
from bs4 import BeautifulSoup
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Converter, MemberConverter
from discord.ext.commands.cooldowns import BucketType


class RegionConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            return league.Regions.get(argument.lower(), league.Regions.na)
        except KeyError:
            return league.Regions.na


class ChampionConverter(Converter):
    async def convert(self, ctx, argument):
        league_client = ctx.cog.league_client
        if argument.isdigit():
            return await league_client.get_champion_by_id(cid=argument)
        else:
            return await league_client.get_champion_by_name(name=argument)


class SummonerConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            member = await MemberConverter().convert(ctx, argument)
            member_data = await ctx.get_user_data(member)
            return member_data.connections.get("league")
        except:
            if str(argument).isalnum():
                return argument


async def league_cache_loaded(ctx):
    league_cog = ctx.cog
    return league_cog.league_client.cache_loaded


class League:
    def __init__(self, bot):
        self.notified = False
        self.bot = bot
        bot.loop.create_task(self.load_cache())
        self.league_client = None  # type: league.Client

    def __unload(self):
        asyncio.ensure_future(self.league_client._session.close(), loop=self.bot.loop)

    async def load_cache(self):
        await self.bot.wait_until_ready()
        self.league_client = league.Client(api_key=self.bot.config['api_keys']['riot'])
        if self.bot.user.id == 180776430970470400:
            await self.league_client.cache_setup()

    def __str__(self):
        return self.__class__.__name__

    # async def __error(self, ctx, error):
    #     if hasattr(error, "original"):
    #         if isinstance(error.original, league.InvalidRegionType):
    #             await ctx.send(str(error.original), delete_after=10)
    #         elif isinstance(error.original, league.NoSummonerFound):
    #             await ctx.send(str(error.original), delete_after=10)
    #     elif isinstance(error, CheckFailure):
    #         if not self.notified:
    #             await ctx.bot.owner.send("League cache is not loaded")
    #             self.notified = True
    #         await ctx.send("League cache not loaded, Owner notified, try again later.")
    #     else:
    #         await ctx.send(str(error.original), delete_after=10)

    async def summoner_history(self, ctx, summoner_name, summoner_region) -> Embed:
        summoner = await self.league_client.get_summoner(summoner_name=summoner_name,
                                                         region=summoner_region)
        history = await summoner.recent_matches()
        embed = Embed(title=f"Iceteabot Match History : {summoner.name} ",
                      description="Returns the summoner's Match History")
        if isinstance(summoner.icon, league.Image):
            embed.set_thumbnail(url=summoner.icon.full_url)
        final_message = ""
        counter = 0
        for ma in history:
            match = await self.league_client.get_match(match_id=ma, region=summoner.region)
            if match.players is None:
                continue
            if counter > 5:
                break
            stats = match.get_participant(summoner)
            result = "\u2705" if stats.stats.win else "\u2620"
            if match.queue_id is not None:
                if hasattr(match.queue_id, "name"):
                    mode = match.queue_id.name.replace('_', ' ').lower()
                else:
                    mode = match.queue_id
            else:
                mode = "Unknown"
            if match.date != 0:
                age = timeago.format(match.date.replace(tzinfo=datetime.timezone.utc),
                                     now=datetime.datetime.now(tz=datetime.timezone.utc))
            else:
                age = "N/A"
            kda = f"{stats.stats.ministats['kills']}/{stats.stats.ministats['deaths']}/" \
                  f"{stats.stats.ministats['assists']}"
            champ = stats.champion
            creep_score = stats.stats.ministats['creepscore']
            final_message += "{0} - {1}, {2}. **{3}** as **{4}** with **{5}CS**\n".format(result, mode, age, kda, champ,
                                                                                          creep_score)
            counter += 1
        embed.add_field(name="Recent Matches:", value=final_message)
        return embed.to_dict()

    async def level_leaderboard(self, ctx, region: str = "all"):
        async with ctx.bot.aioconnection.get(f"https://lolnames.gg/en/highscores/{region}/10/") as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.read(), "lxml")
                leader_board = soup.findChildren("table", {"id": "summoner-names"})
                if leader_board is not None:
                    rows = leader_board[0].findChildren(["th", "tr"])
                    data = []
                    for row in rows:
                        cells = row.findChildren("td")
                        row_data = {}
                        counter = 1
                        for cell in cells[1:4]:
                            if counter == 1:
                                row_data['summoner'] = cell.string
                            elif counter == 2:
                                row_data['region'] = cell.string
                            elif counter == 3:
                                row_data['level'] = cell.string
                            counter += 1
                        if len(row_data) > 0:
                            data.append(row_data)
                    return data

    async def summoner_live(self, ctx, name, region) -> dict:
        summoner = await self.league_client.get_summoner(summoner_name=name, region=region)
        live_game = await summoner.current_match()
        if live_game is not None:
            if live_game.queue_type is not None:
                if hasattr(live_game.queue_type, 'name'):
                    mode = str(live_game.queue_type.name).replace("_", " ").lower()
                elif isinstance(live_game.queue_type, int):
                    mode = live_game.mode.lower()
                else:
                    mode = str(live_game.queue_type).replace("_", " ").lower()
            else:
                mode = "Unknown Gametype"
            embed = Embed(title=f"Iceteabot Live Game Viewer: {summoner.name} ",
                          description=f"**{mode}**")
            for team, players in live_game.get_teams().items():
                player_field = ""
                rank_field = ""
                win_rate_field = ""
                bans_field = ""
                for player in players:
                    player_summoner = await self.league_client.get_summoner(summoner_id=player.sid)
                    player_ranked_data = await player_summoner.ranked_data()
                    champ_emoji = discord.utils.get(ctx.bot.emojis, name=player.id.name.
                                                    replace(" ", "").replace(".", "_").replace("'", "_"))
                    player_field += f"{champ_emoji or player.id}{player_summoner.name[:7]}\n"
                    if player_ranked_data is not None and len(player_ranked_data) > 0:
                        tier_emoji = discord.utils.get(ctx.bot.emojis, name=f"{player_ranked_data[0].tier}".lower())
                        rank_field += f"▫ {tier_emoji or player_ranked_data[0].tier} {player_ranked_data[0].rank} " \
                                      f"({player_ranked_data[0].league_points})\n"
                        win_rate_field += f"▫ {player_ranked_data[0].winrate}% {player_ranked_data[0].total_played}G\n"
                    else:
                        rank_field += "▫ N/A\n"
                        win_rate_field += f"▫ N/A\n"
                if live_game.bans:
                    bans = []
                    for champ in live_game.bans:
                        if champ['champion'] is not None and champ['teamid'] == team:
                            if isinstance(champ['champion'], league.Champion):
                                champ_emoji = discord.utils.get(ctx.bot.emojis, name=champ['champion'].name.
                                                                replace(" ", "").replace(".", "_").replace("'", "_"))
                                if champ_emoji is None:
                                    bans.append(str(champ['champion']))
                                else:
                                    bans.append(str(champ_emoji))
                            else:
                                bans.append(str(champ['champion']))
                        else:
                            bans.append(" ")
                    bans_field += " ".join(bans)
                embed.add_field(name="Players", value=player_field)
                embed.add_field(name="Rank", value=rank_field)
                embed.add_field(name="Winrate", value=win_rate_field)
                if live_game.bans:
                    embed.add_field(name="Bans", value=bans_field, inline=False)
            return embed.to_dict()
        else:
            return {}

    async def summoner_info(self, ctx, name, region) -> Embed:
        summoner = await self.league_client.get_summoner(summoner_name=name, region=region)
        if summoner is not None:
            match_data = None
            top_champions = await summoner.champion_masteries()
            ranked_data = await summoner.ranked_data()
            match_history = await summoner.recent_matches()
            if match_history is not None:
                match_data = [await self.league_client.get_match(match_id=match) for match in
                              match_history]
                wins = sum([m.get_participant(summoner=summoner).stats.win for m in match_data])
                win_rate = float(round((wins / len(match_data)) * 100, 2))
            embed = Embed(title=f"{summoner.name} summoner Information")
            if isinstance(summoner.icon, league.Image):
                embed.set_thumbnail(url=summoner.icon.full_url)
            embed.add_field(name="Level/Region", value=f"{summoner.level}/{summoner.region.name.upper()}")
            embed.add_field(name="Last Games",
                            value=f"{len(match_data)}G {wins}W {len(match_data) - wins}L / {win_rate} % WR")
            if top_champions is not None:
                champ1_emoji = discord.utils.get(ctx.bot.emojis,
                                                 name=top_champions[0].champion.name.replace(" ", "").replace(".",
                                                                                                              "_").replace(
                                                     "'", "_")) or ""
                champ2_emoji = discord.utils.get(ctx.bot.emojis,
                                                 name=top_champions[1].champion.name.replace(" ", "").replace(".",
                                                                                                              "_").replace(
                                                     "'", "_")) or ""
                champ3_emoji = discord.utils.get(ctx.bot.emojis,
                                                 name=top_champions[2].champion.name.replace(" ", "").replace(".",
                                                                                                              "_").replace(
                                                     "'", "_")) or ""
                embed.add_field(name="Top Champions",
                                value=f"{champ1_emoji}**[{top_champions[0].level}]** 1. **{top_champions[0].champion}** : "
                                      f"{top_champions[0].points:,}\n"
                                      f"{champ2_emoji}**[{top_champions[1].level}]** 2. **{top_champions[1].champion}** : "
                                      f"{top_champions[1].points:,}\n"
                                      f"{champ3_emoji}**[{top_champions[2].level}]** 3. **{top_champions[2].champion}** : "
                                      f"{top_champions[2].points:,}\n")
            if ranked_data is not None:
                if ranked_data:
                    tier_emoji = discord.utils.get(ctx.bot.emojis, name=ranked_data[0].tier.lower()) or ""
                    embed.add_field(name="Ranked Stats",
                                    value=f"{tier_emoji} {ranked_data[0].tier} {ranked_data[0].rank}\n{ranked_data[0].league_points}LP "
                                          f"{ranked_data[0].wins}W {ranked_data[0].losses}L\nWinrate: {ranked_data[0].winrate}%")
                else:
                    tier_emoji = "<a:loading:393852367751086090>"
                    embed.add_field(name="Ranked Stats", value=f"{tier_emoji} N/A")
            # match_history_template = "**[{0}]** {1}, {2}. **{3}/{4}/{5}** as **{6}** with **{7}CS**\n"
            # match_history_response = ""
            # if match_data is not None:
            #     for match in match_data[:6]:
            #         participant_data = match.get_participant(summoner=summoner)
            #         match_history_response += match_history_template.format(
            #             "V" if participant_data.stats.win else "D",
            #             match.queue_id.type.replace("_", " ").lower(),
            #             timeago.format(match.date.replace(tzinfo=datetime.timezone.utc),
            #                            now=datetime.datetime.now(tz=datetime.timezone.utc)),
            #             participant_data.stats.ministats['kills'],
            #             participant_data.stats.ministats['deaths'],
            #             participant_data.stats.ministats['assists'],
            #             participant_data.champion,
            #             participant_data.stats.ministats['creepscore']
            #         )
            # embed.add_field(name="Recent Matches", value=match_history_response)
            embed.add_field(name="More details",
                            value=f"[OP.GG](https://{summoner.region.name.lower()}.op.gg/summoner/userName={summoner.name.replace(' ','')}) "
                                  f"\U00002022 [LOLking](http://www.lolking.net/queue/na/{summoner.name.replace(' ','+')}/{summoner.name.replace(' ','')}#/profile) ")
            return embed.to_dict()

    async def get_champion_mastery_leaderboard(self, ctx, champion) -> Embed:
        data = await self.get_champ_mastery_leaderboard(ctx.bot.aioconnection, champion)
        embed = Embed(title=f"Mastery Leaderboard for {champion}")
        rank = ""
        name_sever = ""
        points = ""
        for player in data[:9]:
            if len(player['name']) > 10:
                player_name = player['name'][:7] + "..."
            else:
                player_name = player['name']
            name_sever += f"{player_name} | {player['server']}\n"
            rank += f"{player['rank']}\n"
            points += f"{player['points']}\n"
        embed.add_field(name="Name/Server", value=name_sever)
        embed.add_field(name="Rank", value=rank)
        embed.add_field(name="Points", value=points)
        return embed

    async def get_summoner_mastery_list(self, ctx, name, region) -> Embed:
        summoner = await self.league_client.get_summoner(summoner_name=name, region=region)
        masteries = await summoner.champion_masteries()
        embed = Embed(title=f"Iceteabot Mastery stats : {summoner.name} ",
                      description="Returns the summoner's top 10 champion masteries")
        champion_points = ""
        last_played = ""
        chest_status = ""
        total_level = sum([champ.level for champ in masteries])
        total_champs = len(masteries)
        total_points = "{:,}".format(sum([champ.points for champ in masteries]))
        for champ in range(0, 9):
            champ_emoji = discord.utils.get(ctx.bot.emojis,
                                            name=masteries[champ].champion.name.replace(" ", "").replace(".",
                                                                                                         "_").replace(
                                                "'", "_")) or ""
            champ_level = masteries[champ].level
            champ_name = masteries[champ].champion
            champ_points = "{:,}".format(masteries[champ].points)
            champion_points += f"**[{champ_level}]**{champ_emoji}**{champ_name}** - {champ_points}\n"
            last_played += f"▫ {timeago.format(masteries[champ].last_played.replace(tzinfo=datetime.timezone.utc),now=datetime.datetime.now(tz=datetime.timezone.utc))}\n"
            chest_status += f"{'✅' if masteries[champ].chest_granted else '❌'} | " \
                            f"{'Mastered' if masteries[champ].level == 7 else f'{masteries[champ].tokens} Tokens'}\n"
        embed.add_field(name="Champion/Points", value=champion_points)
        embed.add_field(name="Last Played", value=last_played)
        embed.add_field(name="Chest/Status", value=chest_status)
        embed.add_field(name="Totals", value=f"**Champs:** {total_champs} \u2022 **Mastery Level:** {total_level} "
                                             f"\u2022 **Mastery Points:** {total_points}", inline=False)
        return embed.to_dict()

    async def get_champ_mastery_leaderboard(self, session, champion: str) -> list:
        async with session.get(f"https://www.masterypoints.com/highscores/champion/{champion}") as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.read(), 'lxml')
                match = soup.find_all('tr', {"itemprop": "itemListElement"})
                data = []
                for champ in match:
                    sum_name = champ.find("span", {"itemprop": "name"}).text.strip("\n")
                    points = champ.find("span", {"class": "text-bigger"}).text
                    rank = champ.find("div", {"class": "floatleft paddingleft"}).find("span",
                                                                                      {"class": "small"}).text.strip(
                        "\n")
                    server = champ.find("td", {
                        "class": "hidden-xs"}).find_next_sibling().find_next_sibling().find_next_sibling().text.strip(
                        "\n")
                    data.append({
                        "name": sum_name,
                        "points": points,
                        "rank": rank,
                        "server": server,
                    })
                    continue
                return data

    @staticmethod
    async def function_caller(ctx, target, region):
        if target is None:
            user_data = await ctx.user_data()
            if user_data.connections.get("league", False):
                target = user_data.connections['league']['summoner']
                region = user_data.connections['league']['region']
                region = await RegionConverter().convert(ctx, region)
            else:
                await ctx.send("User has not set league credentials")
                return None, None
            return target, region
        else:
            return target, region

    @commands.command()
    @commands.check(league_cache_loaded)
    @commands.cooldown(30, 1, BucketType.user)
    async def lolprofile(self, ctx, username: SummonerConverter = None, region: RegionConverter = league.Regions.na):
        """
        Default region = NA

        eg:
        lolprofile RiotPhreak
        or
        lolprofile HideonBush kr

        Alternative Methods:
            lolprofile @iceteabot
        If username is left blank then it will use your own credentials from the database if linked




        """
        username, region = await self.function_caller(ctx, username, region)
        if username is None:
            return
        async with ctx.typing():
            data = await self.summoner_info(ctx, username, region)
            if data is None:
                await ctx.send("Could not find any data")
            embed = discord.Embed().from_data(data=data)
            embed.colour = ctx.author.top_role.color
            embed.set_footer(text=f"{ctx.author.display_name} | {ctx.message.created_at.strftime('%c')}",
                             icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)

    @commands.command(aliases=['recent'])
    @commands.cooldown(30, 1)
    @commands.check(league_cache_loaded)
    async def lolhistory(self, ctx, username: SummonerConverter = None, region: RegionConverter = league.Regions.na):
        """

        Default region = NA

        eg:
        lolhistory RiotPhreak
        or
        lolhistory HideonBush kr

        Alternative Methods:
            lolhistory @iceteabot

        If league account is linked to the bot and usernname is left blank it will display your history.

        To link league account to the bot see ``help connections league``


        """
        username, region = await self.function_caller(ctx, username, region)
        if username is None:
            return
        async with ctx.typing():
            data = await self.summoner_history(ctx, username, region)
            embed = discord.Embed().from_data(data=data)
            embed.colour = ctx.author.top_role.color
            embed.set_footer(text=f"{ctx.author.display_name} | {ctx.message.created_at.strftime('%c')}",
                             icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)

    @commands.command()
    @commands.check(league_cache_loaded)
    @commands.cooldown(30, 1, BucketType.user)
    async def lollive(self, ctx, username: SummonerConverter = None, region: RegionConverter = league.Regions.na):
        """
        Default region = NA

        eg:
        lollive RiotPhreak
        or
        lollive HideonBush kr

        Alternative Methods:
            lollive @iceteabot

        If league account is linked to the bot and usernname is left blank it will display your history.

        To link league account to the bot see ``help connections league``
        """
        username, region = await self.function_caller(ctx, username, region)
        if username is None:
            return
        async with ctx.typing():
            data = await self.summoner_live(ctx, username, region)
            if len(data) == 0:
                await ctx.send("Player not in game")
                return
            new_embed = discord.Embed().from_data(data=data)
            new_embed.colour = 0x0066ff
            new_embed.set_footer(text=f"{ctx.author.display_name} | {ctx.message.created_at.strftime('%c')}",
                                 icon_url=ctx.author.avatar_url)
            await ctx.send(embed=new_embed)

    @commands.command(aliases=['lolmasteries'])
    @commands.check(league_cache_loaded)
    @commands.cooldown(30, 1, BucketType.user)
    async def lolmstats(self, ctx, username: SummonerConverter = None, region: RegionConverter = league.Regions.na):
        """

        Default region = NA

        eg:
        lolmstats RiotPhreak
        or
        lolmstats HideonBush kr

        Alternative Methods:
            lolmstats @iceteabot

        If league account is linked to the bot and usernname is left blank it will display your history.

        To link league account to the bot see ``help connections league``
        """
        username, region = await self.function_caller(ctx, username, region)
        if username is None:
            return
        async with ctx.typing():
            embed = discord.Embed().from_data(await self.get_summoner_mastery_list(ctx, username, region))
            embed.color = ctx.author.top_role.color
            embed.set_footer(text=f"{ctx.author.display_name} | {ctx.message.created_at.strftime('%c')}",
                             icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)

    #
    # @commands.command(name="lstats")
    # @commands.check(permissions.bot_administrator)
    # async def lolapistats(self, ctx, region: str = 'na1'):
    #     """Displays api endpoint request statuses counter. Used to keep track of how many responses the bot is recieveing
    #     Requires administrator permissions"""
    #     await ctx.send(self.obj.regional_connections[region].requests_counter)

    # @commands.command(name='lstatus')
    # @commands.cooldown(5, 1)
    # async def lolstatus(self, ctx, region: str = 'na1'):
    #     """Returns an embed detailing any server/game issues"""
    #     async with ctx.channel.typing():
    #         embed = await self.obj.get_league_status(region=region)
    #         embed.color = 0x0066ff
    #         embed.set_footer(text=f"{ctx.author.display_name} | {ctx.message.created_at.strftime('%c')}",
    #                          icon_url=ctx.author.avatar_url)
    #         await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(5, 1)
    @commands.check(league_cache_loaded)
    async def loltopplayers(self, ctx, champion: ChampionConverter):
        """Displays the top champion masteries for a specified champion"""
        async with ctx.typing():
            embed = await self.get_champion_mastery_leaderboard(ctx, champion)
            if embed is not None:
                embed.colour = 0x0066ff
                embed.set_footer(text=f"{ctx.author.display_name} | Data via masterypoints.com",
                                 icon_url=ctx.author.avatar_url)
                await ctx.send(embed=embed)

    @commands.command(aliases=['lolfree2play', 'lolfree', "lolrotation"])
    @commands.check(league_cache_loaded)
    async def freetoplay(self, ctx):
        """Displays the weekly free rotation"""

        free_champions = [champ for champ in self.league_client.static_cache['champions'].values() if champ.free]
        embed = discord.Embed(title=f"{ctx.guild.me.display_name}: Free Rotation")
        champ_emojis = []
        for champ in free_champions:
            champ_emoji = discord.utils.get(ctx.bot.emojis,
                                            name=champ.name.replace(" ", "").replace(".", "_").replace("'", "_"))
            champ_emojis.append((str(champ_emoji), champ.name))
        embed.add_field(name="\u200b",
                        value="\n".join(["{0} **{1}**".format(emoji, champ) for emoji, champ in champ_emojis[:7]]))
        embed.add_field(name="\u200b",
                        value="\n".join(["{0} **{1}**".format(emoji, champ) for emoji, champ in champ_emojis[7::]]))
        await ctx.send(embed=embed)

    @commands.command(name="lolloadcache")
    @commands.is_owner()
    async def load_cache_command(self, ctx, locale="en_US"):
        await self.league_client.cache_setup(locale=locale)
        await ctx.send("Cache loaded")

    @commands.command(name="levelleaderboard", aliases=['lvhs', "lvlb"])
    @commands.cooldown(30, 1)
    @commands.check(league_cache_loaded)
    async def level_leader_board(self, ctx, region: RegionConverter = None):
        """Displays the top 5 highest summoners by level

        If region is left blank displays worldwide rankings

        """
        data = await self.level_leaderboard(ctx, region.name if isinstance(region, league.Regions) else "all")
        embed = discord.Embed(color=0xD629D4)
        if data is not None:
            for row in data[:5]:
                embed.add_field(name="Summoner", value=row['summoner'])
                embed.add_field(name="Region", value=row['region'])
                embed.add_field(name="level", value=row['level'])
            embed.set_footer(text="Data provided by lolnames.gg")
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(League(bot))
