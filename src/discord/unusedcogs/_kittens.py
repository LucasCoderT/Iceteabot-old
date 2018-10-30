from src.discord.utils.permissions import *
from src.discord.utils import errors
from src.games.exploding_kittens import IceKittens, InvalidActionException
from discord.ext import commands


# TODO revamp game to create temp channels instead of having dedicated channels. Or allow the admins to pick.

async def game_created(self, ctx):
    if ctx.guild.id in self.games:
        return True
    else:
        raise EKGameNotCreated


async def game_open(self, ctx):
    if self.games[ctx.guild.id]['open'] and (len(self.games[ctx.guild.id]['players']) + 1) < 6:
        return True
    else:
        raise EkGameNotOpen


class Kittens:
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    async def __local_check(self, ctx):
        return any([await bot_administrator(ctx), await guild_administrator(ctx), await ctx.bot.is_owner(ctx.author)])

    def __str__(self):
        return self.__class__.__name__

    @commands.group()
    @commands.guild_only()
    async def ek(self, ctx):
        """Base command of exploding kittens"""
        pass

    @ek.error
    async def _ekerror(self, ctx, error):
        if isinstance(error, errors.WrongChannel):
            await ctx.send("Invalid channel")

    @ek.command()
    @commands.check(channel_check)
    @commands.bot_has_permissions(read_messages=True, send_messages=True, manage_messages=True,
                                  read_message_history=True, manage_channel=True)
    @commands.guild_only()
    async def open(self, ctx):
        """Opens a game for others to join in
        You are only allowed 1 game per server"""
        if ctx.guild in self.games:
            raise EkGameAlreadyExists
        else:
            self.games[ctx.guild] = {"open": True, "players": [], 'host': ctx.author,
                                     'game': None}
            await ctx.send(f"{ctx.author.mention} has opened an Exploding Kittens game! use !ek join to join the game")

    @open.error
    async def _openerror(self, ctx, error):
        if isinstance(error, errors.WrongChannel):
            await ctx.send("Invalid channel")
        elif isinstance(error, errors.EkGameAlreadyExists):
            await ctx.send("There already exists a game in this server, "
                           "there can only be 1 game per server. If this is a mistake, "
                           "contact a moderator to use !ek clear")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("I'm missing my required permissions to start a game")

    @ek.command()
    @commands.check(channel_check)
    @commands.check(bot_moderator)
    @commands.guild_only()
    async def clear(self, ctx):
        """Removes the current game, used if the entry is bugged or a current game is in a stale mate"""
        self.games.pop(ctx.message.server)
        if ctx.guild not in self.games:
            await ctx.send("The game has been cleared")

    @clear.error
    async def _clearerror(self, ctx, error):
        if isinstance(error, errors.WrongChannel):
            await ctx.send("Invalid channel")
        elif isinstance(error, errors.NotModerator):
            await ctx.send("You require Moderator permissions to access this command")

    @ek.command()
    @commands.check(game_open)
    @commands.check(channel_check)
    @commands.guild_only()
    async def join(self, ctx):
        """The command to join the currently open game"""
        self.games[ctx.guild]['players'].append(ctx.author)
        await ctx.send(
            "{0.message.author.mention} has joined the game, "
            "there is now {1} people in this game".format(ctx,
                                                          len(self.games[ctx.guild]['players'])))

    @join.error
    async def _joinerror(self, ctx, error):
        if isinstance(error, errors.EkGameNotOpen):
            await ctx.send("No Game currently open")
        elif isinstance(error, errors.WrongChannel):
            await ctx.send("Cannot use this command in this channel")

    @ek.command()
    @commands.check(game_created)
    @commands.check(channel_check)
    @commands.guild_only()
    async def start(self, ctx):
        """Can only be used by the host and is used to close the join option and start the game"""
        if ctx.author == self.games[ctx.guild]['host']:
            if len(self.games[ctx.guild]['players']) == 1:
                await ctx.send("You wanna play by yourself?\nYou need a least 2 people to play a game")
            else:
                self.games[ctx.guild]['open'] = False
                await ctx.channel.purge(limit=1000)
                await ctx.send("The game is starting. I will explain the rules now")
                await asyncio.sleep(3)
                embed = discord.Embed(title="Iceteakittens rules", colour=0xfdff00,
                                      description="Explaining the rules of the game",
                                      url="https://www.explodingkittens.com/explodingkittensrules.pdf")
                embed.add_field(name="Objective",
                                value="``Be the last one standing``\n")
                embed.add_field(name="Notes:", value="Everyone only starts with a defuse", inline=False)
                embed.add_field(name='Game Commands',
                                value=
                                "**Commands are not prefixes by anything**\n "
                                "**Case is not important**\n "
                                "``draw``\n "
                                "``use <card>``\n "
                                "**NOTE**: combo commands:\n "
                                "``use 2 of a kind`` | ``two of a kind``\n "
                                "``use 3 of a kind`` | ``three of a kind``\n "
                                "``use 5 cards`` ~ Pick something from the discard pile")
                embed.add_field(name="Warnings", value="``Players have infinite time per turn``")
                msg1 = await ctx.send(embed=embed)
                await msg1.pin()
                await ctx.send("The game will start in **10 seconds**, GLHF :smile:")
                await asyncio.sleep(10)
                self.games[ctx.guild]['game'] = IceKittens(self.bot, ctx.channel,
                                                            self.games[ctx.guild][
                                                               'players'])
                game = self.games[ctx.guild]['game']
                await game.generate_hands()
                for player in game.players:
                    game.hand_messages[player] = await player.send(
                        f"Your hand:\n```{', '.join(game.players[player])}```")
                    await game.hand_messages[player].pin()
                server_object = await ctx.bot.icethinkdb.get_guild(ctx.guild.id)
                message = await ctx.send(f"There is **{len(game.deck)}** cards left")
                await message.pin()
                current_player = 0
                while len(game.players) > 1 and ctx.guild in self.games:
                    current_player += game.reversed
                    current_player %= len(game.players)
                    player = game.player_order[current_player]
                    await message.edit(content=f"There is **{len(game.deck)}** cards left")
                    if player in game.dead_players:
                        continue
                    await game.new_turn(player)
                    if game.deck[0] == "imploding kitten":
                        await ctx.send("The next card is an imploding kitten, GL")

                    def check(m):
                        return str(m.channel.id) == server_object.game_room and m.author == player

                    while game.turn_finished is False and ctx.guild in self.games:
                        try:
                            await ctx.send("It is currently {0.mention}'s turn".format(player))
                            action = await self.bot.wait_for("message", check=check)
                            if action.content.lower().startswith('draw'):
                                await game.draw()
                                if game.turns == 0:
                                    break
                            elif action.content.lower().startswith('use'):
                                card_action = action.content.lower().split()
                                if " ".join(card_action[1::]) in ['2 of a kind',
                                                                  'two of a kind']:
                                    await game.twocards(ctx)
                                elif " ".join(card_action[1::]) in ['3 of a kind'
                                                                    'three of a kind', ]:
                                    await game.threecards(ctx)
                                elif " ".join(card_action[1::]) in ['5 cards']:
                                    await game.fivecards(ctx)
                                elif " ".join(card_action[1::]) in game.players[player]:
                                    await game.action(ctx, " ".join(card_action[1::]))
                                    if game.turns == 0:
                                        break
                                else:
                                    await ctx.send(f"You do not have a {' '.join(card_action[1::])}, continuing...")
                            elif action.content.lower().startswith('view'):
                                await action.author.send(f"Your hand:\n```{', '.join(game.players[player])}```")
                        except InvalidActionException:
                            await ctx.send("Invalid input, try again")
                if ctx.guild in self.games:
                    for message in game.hand_messages.values():
                        await message.delete()
                    await ctx.send(
                        f"Congratulations {game.players[0].mention} "
                        f"on winning \U0001F44F \U0001F44F \U0001F44F")
                    self.games.pop(ctx.guild)
                    await ctx.send("That concludes this game of IceKittens! Hope you enjoyed :smiley:")
        else:
            ctx.send("Only the host(the person who first used !ek create) can use this command")

    @start.error
    async def start_error(self, error, ctx):
        if isinstance(error, errors.EKGameNotCreated):
            await ctx.send("No Game has been created, use ``ek open`` to create a game")
        elif isinstance(error, errors.WrongChannel):
            await ctx.send("Cannot use this command in this channel")


def setup(bot):
    bot.add_cog(Kittens(bot))
