import asyncio
import random

possible_actions = ['see the future', 'shuffle', 'favor', 'skip', 'attack', 'alter the future',
                    'targeted attack', 'draw from the bottom', 'pink', 'brown', 'reverse', 'black', 'blue',
                    'purple', 'orange', 'dark brown', '2 of a kind', 'two of a kind', '3 of a kind', 'three of a kind',
                    '5cards', 'green']


class TooManyPlayersException(Exception):
    def __init__(self):
        Exception.__init__(self, "This game does not support this many players")


class NotEnoughPlayersException(Exception):
    def __init__(self):
        Exception.__init__(self, "This game does not support solo play")


class InvalidActionException(Exception):
    def __init__(self):
        Exception.__init__(self, "Invalid action, try again")


class IceKittens:
    def __init__(self, bot, channel, players: list, expansion: bool = True):
        """IceKittens Game Object"""
        # Checks if the amount of players is greater than 6 or only 1
        self.bot = bot
        self.channel = channel
        if len(players) > 6:
            raise TooManyPlayersException
        elif len(players) == 1:
            raise NotEnoughPlayersException
        else:
            self.expansion = expansion
            # Creates the decks, original and expansion. Allows ppl to play standard or exp if they wish
            self.original = {"cats schrodinger": 4, "shy bladder cat": 4, "momma cat": 4, "zombie cat": 4,
                             "bikini cat": 4, "see the future": 5, "shuffle": 4, "favor": 4, "skip": 4, "attack": 4,
                             "nope": 5, "defuse": 6}
            self.exp_pack = {"alter the future": 4, "blank cat": 4, "targeted attack": 3, "draw from the bottom": 4,
                             'reverse': 4}
            self.deck = []
            if expansion:
                cards = {**self.original, **self.exp_pack}
                deck = [[card] * cards[card] for card in cards]
                for c in deck:
                    for cv in c:
                        self.deck.append(cv)
            else:
                cards = {**self.original}
                deck = [[card] * cards[card] for card in cards]
                for c in deck:
                    for cv in c:
                        self.deck.append(cv)
            self.players = {player: [] for player in players}
            self.hand_messages = {}
            self.player_order = [player for player in players]
            self.player_index = 0
            self.reversed = 1
            self.discard = []
            self.attack_counter = 0
            self.current_player = None
            self.target = None
            self.last_played = None
            self.implodingkitten = False
            self.turn_finished = False
            self.dead_players = []
            self.turns = 1

    async def new_turn(self, next_player):
        if self.last_played in ['attack', 'targeted attack']:
            self.turns = 2
        else:
            self.turns = 1
        self.current_player = next_player
        self.turn_finished = False
        self.target = None

    async def action(self, ctx, action: str):
        if action in possible_actions:
            if action in ['see the future', 'pink']:
                await self.seethefuture(ctx)
            elif action in ['shuffle', 'brown']:
                await self.shuffle(ctx)
            elif action in ['favor', 'black']:
                await self.favor(ctx)
            elif action in ['skip', 'blue']:
                await self.skip(ctx)
            elif action in ['reverse', 'green']:
                await self.reverse(ctx)
            elif action in ['targeted attack', 'orange']:
                await self.targetattack(ctx)
            elif action in ['attack', 'yellow']:
                await self.attack(ctx)
            elif action in ['alter the future', 'purple']:
                await self.alter_the_future(ctx)
            elif action in ['draw from the bottom', 'dark brown']:
                await self.drawfrombottom(ctx)
            else:
                raise InvalidActionException
        else:
            raise InvalidActionException

    async def generate_hands(self, single: bool = True):
        for player, hand in self.players.items():
            if single:
                pass
            else:
                randomed_cards = random.sample(self.deck, 4)
                for card in randomed_cards:
                    hand.append(card)
                    self.deck.remove(card)
            hand.append("defuse")
            self.deck.remove("defuse")
        bombs = ["exploding kitten"] * (len(self.players) - 1)
        self.deck += bombs
        if self.expansion and len(self.players) > 5:
            self.deck += ["imploding kitten"]
        random.shuffle(self.deck)

    async def draw(self):
        card_drawn = self.deck[0]
        if card_drawn == "imploding kitten":
            await self.imploding()
        elif card_drawn == "exploding kitten":
            await self.exploding()
        else:
            self.players[self.current_player].append(card_drawn)
            del self.deck[0]
            await self.hand_messages[self.current_player].edit(
                content=f"Your hand:\n```{', '.join(self.players[self.current_player])}```")
            self.turns -= 1

    async def seethefuture(self, ctx):
        self.players[self.current_player].remove('see the future')
        self.discard.append('see the future')
        self.last_played = "see the future"
        if await self.nope() is False:
            await ctx.send(f"{self.current_player.display_name} has used See the future ")
            cards = self.deck[0:3]
            await self.current_player.send(f"The next cards are ``{', '.join(cards)}``")

    async def shuffle(self, ctx):
        self.players[self.current_player].remove('shuffle')
        self.discard.append('shuffle')
        self.last_played = "shuffle"
        if await self.nope() is False:
            await ctx.send(f'{self.current_player.display_name} has Shuffled the deck')
            random.shuffle(self.deck)

    def target_check(self, m):
        return m.channel == self.channel and m.author == self.current_player and len(
            m.mentions) == 1 and m.mentions[
                                     0] in self.players

    async def favor(self, ctx):
        self.players[self.current_player].remove('favor')
        self.discard.append('favor')
        self.last_played = 'favor'
        if await self.nope() is False:
            await ctx.send("Mention your target now")
            target = await self.bot.wait_for('message', check=self.target_check)
            self.target = target.mentions[0]
            await ctx.send(
                f'{self.current_player.display_name} has asked {target.mentions[0].display_name} for a favor')
            while True:
                await target.send("Enter card name to give")
                card = await self.bot.wait_for('message', check=self.alter_check)
                if card is None:
                    await target.send("You don't have that card")
                else:
                    self.players[self.target].remove(card)
                    self.player_order[self.current_player].append(card)
                    await self.hand_messages[self.current_player].edit(
                        content=f"Your hand:\n```{', '.join(self.players[self.current_player])}```")
                    break

    async def skip(self, ctx):
        self.players[self.current_player].remove('skip')
        self.discard.append('skip')
        self.last_played = 'skip'
        if await self.nope() is False:
            await ctx.send(f'{self.current_player.display_name} has used skip')
            self.last_played = 'skip'
            self.turns -= 1

    def alter_check(self, message):
        return message.author == self.current_player.dm_channel.recipient \
               and message.channel == self.current_player.dm_channel

    async def alter_the_future(self, ctx):
        self.players[self.current_player].remove('alter the future')
        self.discard.append('alter the future')
        self.last_played = 'alter the future'
        if await self.nope() is False:
            await ctx.send(f'{self.current_player.display_name} has used alter the future')
            await self.current_player.send(
                f"the next 3 cards are: ```py\n{self.deck[0]} : 0\n{self.deck[1]} : 1\n{self.deck[2]} : 2\n```")
            await self.current_player.send(
                f"to reorder the cards type(in a PM) the order using the numbers provided "
                f"separated by spaces\n**(0 is the next card up)**\n"
                f"eg: 1 0 2")
            async with ctx.typing():
                new_order = await self.bot.wait_for('message', check=self.alter_check)
                items = new_order.content.split()
                new_deck = []
                if all([item.isdigit() for item in items]):
                    for item in items:
                        if int(item) == 0:
                            new_deck.append(self.deck[0])
                        elif int(item) == 1:
                            new_deck.append(self.deck[1])
                        elif int(item) == 2:
                            new_deck.append(self.deck[2])
                    del self.deck[0:2]
                    self.deck = new_deck + self.deck
            await self.channel.send("Finished Alter the Future, continuing on...")

    async def attack(self, ctx):
        self.players[self.current_player].remove('attack')
        self.discard.append('attack')
        self.last_played = 'attack'
        if self.attack_counter != 1:
            if await self.nope() is False:
                await ctx.send(f'{self.current_player.display_name} has used attack')
                self.attack_counter += 1
                self.last_played = 'attack'
                self.turn_finished = True
        elif self.attack_counter == 1:
            await ctx.send(f'{self.current_player.display_name} has used attack')
            self.attack_counter += 1
            self.last_played = 'attack'
            self.turn_finished = True

    async def targetattack(self, ctx):
        self.players[self.current_player].remove('targeted attack')
        self.discard.append('targeted attack')
        self.last_played = 'targeted attack'
        if self.attack_counter != 1:
            if await self.nope() is False:
                await ctx.send("Mention your target now")
                target = await self.bot.wait_for('message', check=self.target_check)
                self.target = target.mentions[0]
                await ctx.send(
                    f'{self.current_player.mention} has used targeted attack on {self.target.display_name}')
                self.attack_counter += 1
                self.turn_finished = True
        elif self.attack_counter == 2:
            await ctx.send("Mention your target now")
            target = await self.bot.wait_for('message', check=self.target_check)
            self.target = target.mentions[0]
            await ctx.send(
                f'{self.current_player.mention} has used targeted attack on {self.target.display_name}')
            self.attack_counter = 0
            self.turn_finished = True

    async def drawfrombottom(self, ctx):
        self.players[self.current_player].remove('draw from the bottom')
        self.discard.append('draw from the bottom')
        self.last_played = 'draw from the bottom'
        if await self.nope() is False:
            await ctx.send(f'{self.current_player.display_name} has used draw from the bottom')
            bottom_card = self.deck[-1]
            self.players[self.current_player].append(self.deck[-1])
            del self.deck[-1]
            if bottom_card in ['exploding kitten']:
                await self.exploding()
            elif bottom_card in ['imploding kitten']:
                await self.imploding()
            else:
                await self.hand_messages[self.current_player].edit(
                    content=f"Your hand:\n```{', '.join(self.players[self.current_player])}```")
            self.turn_finished = True

    async def reverse(self, ctx):
        self.players[self.current_player].remove('reverse')
        self.discard.append('reverse')
        self.last_played = 'reverse'
        if await self.nope() is False:
            await ctx.send(f'{self.current_player.display_name} has reversed the game!')
            if len(self.players) == 2:
                pass
            else:
                self.reversed *= -1
            self.turn_finished = True

    def card_check(self, message):
        return message.channel == self.channel and message.author == self.current_player

    def two_card_check(self, message):
        return message.content.isdigit() and int(message.content) < len(self.players[self.target]) and int(
            message.content) >= 0 and message.author == self.target

    async def twocards(self, ctx):
        cards = []
        while not len(cards) == 2:
            await ctx.send("Enter card name to use, if you wish to cancel this move, type ``cancel``")
            selected_card = await self.bot.wait_for('message', check=self.card_check)
            if selected_card.content.lower().startswith("cancel"):
                await ctx.send(f"{self.current_player.display_name} has cancelled two of a kind")
                return
            elif selected_card.content in self.players[self.current_player]:
                if selected_card.content in cards or len(cards) == 0 or selected_card.content == "blank cat":
                    cards.append(selected_card.content)
                    await ctx.send(f"Success, {2 - len(cards)} to go ")
                else:
                    await ctx.send("Failure, try again")
        for card in cards:
            self.players[self.current_player].remove(card)
        await ctx.send("Finished adding cards..")
        await ctx.send("Mention your target now")
        message = await self.bot.wait_for('message', check=self.target_check)
        self.target = message.mentions[0]
        if await self.nope() is False:
            await ctx.send(f"Enter a number between 0-{len(self.players[self.target])}")
            selection = await self.bot.wait_for('message', check=self.two_card_check)
            card = self.players[self.target][selection]
            self.players[self.target].remove(card)
            self.players[self.current_player].append(card)

    def threecard_check(self, message):
        return message.channel == self.channel and message.author == self.current_player

    async def threecards(self, ctx):
        cards = []
        while not len(cards) == 3:
            await ctx.send("Enter card name to use, if you wish to cancel this move, type ``cancel``")
            selected_card = await self.bot.wait_for('message', check=self.card_check)
            if selected_card.content.lower().startswith("cancel"):
                return
            elif selected_card.content in self.players[self.current_player]:
                if selected_card.content in cards or len(cards) == 0 or selected_card.content == "blank cat":
                    cards.append(selected_card.content)
                    await ctx.send(f"Success, {3 - len(cards)} to go ")
                else:
                    await ctx.send("Failure, try again")
        for card in cards:
            self.players[self.current_player].remove(card)
        await ctx.send("Finished adding cards..")
        await ctx.send("Mention your target now")
        message = await self.bot.wait_for('message', check=self.target_check)
        self.target = message.mentions[0]
        if await self.nope() is False:
            await ctx.send(f"Enter a card name you want")
            selection = await self.bot.wait_for('message', check=self.threecard_check)
            card_name = selection.content.lower()
            if card_name in self.players[self.target]:
                self.players[self.current_player].append(card_name)
                self.players[self.target].remove(card_name)
                ctx.send("Success")
            else:
                ctx.send(f"{self.target.display_name} does not have {selection} :cry:")

    async def fivecards(self, ctx):
        cards = []
        while not len(cards) == 5:
            await ctx.send("Enter card name to use, if you wish to cancel this move, type ``cancel``")
            selected_card = await self.bot.wait_for('message', check=self.card_check)
            card_name = selected_card.content.lower()
            if card_name.startswith("cancel"):
                return
            elif card_name in self.players[self.current_player]:
                if selected_card.content not in cards or selected_card.content == "blank cat":
                    cards.append(card_name)
                    await ctx.send(f"Success, { 5 - len(cards)} to go ")
                else:
                    await ctx.send("Failure, try again")
        for card in cards:
            self.players[self.current_player].remove(card)
        await ctx.send("Finished adding cards..")
        if await self.nope() is False:
            while True:
                await ctx.send(f"Enter a card name you want")
                selection = await self.bot.wait_for('message', check=self.threecard_check)
                card_wanted = selection.content.lower()
                if card_wanted in self.discard:
                    self.players[self.current_player].append(card_wanted)
                    self.discard.remove(card_wanted)
                    await ctx.send("Success")
                    break
                else:
                    await ctx.send(f"The discard pile does not have {card_wanted} :cry:")

    def author_check(self, message):
        return message.author == self.current_player

    def number_check(self, message):
        return message.content.isdigit() and len(
            self.deck) >= int(
            message.content) >= 0 and message.author == self.current_player.dm_channel.recipient \
               and message.channel == self.current_player.dm_channel

    async def imploding(self):
        await self.channel.send(f"{self.current_player.display_name} has drawn a face down imploding kitten")
        self.implodingkitten = True
        del self.deck[0]
        await self.current_player.send(f"Select a deck position to place the bomb back in, between 0-{len(self.deck)}")
        message = await self.bot.wait_for('message', check=self.number_check)
        self.deck.insert(message.content, "imploding kitten")
        self.turn_finished = True

    async def exploding(self):
        await self.channel.send(f"{self.current_player.display_name} **has drawn a bomb!** :skull: :skull: :skull: ")
        del self.deck[0]
        if 'defuse' in self.players[self.current_player]:
            await self.channel.send("Its alright though, he has a defuse!")
            self.players[self.current_player].remove('defuse')
            self.discard.append('defuse')
            await self.current_player.send(f"Select a number 0-{len(self.deck)}")
            message = await self.bot.wait_for('message', check=self.number_check)
            self.deck.insert(int(message.content), 'exploding kitten')
        else:
            self.dead_players.append(self.current_player)
            self.discard.append('exploding kitten')
            self.discard.append([card for card in self.current_player])
            self.players.pop(self.current_player)
            await self.channel.send(
                f":skull: :skull: :skull: {self.current_player.mention} is **out!** :skull: :skull: :skull: ")
        self.turn_finished = True

    def nope_check(self, message):
        return message.author in self.players and message.content.startswith("nope")

    async def nope(self):
        while True:
            try:
                await self.channel.send("Everyone has 5 seconds to nope this action")
                message = await self.bot.wait_for("message", check=self.nope_check, timeout=5)
                if 'nope' in self.players[message.author]:
                    self.players[message.author].remove('nope')
                    self.discard.append('nope')
                    await self.channel.send(
                        f"{message.author.mention} has stopped {self.current_player.display_name}'s {self.last_played}")
                    self.last_played = 'nope'
                else:
                    await self.channel.send("You do not have a nope card, continuing")
                    continue
            except asyncio.TimeoutError:
                await self.channel.send("Continuing...")
                return False


if __name__ == '__main__':
    mygame = IceKittens("asd", "Asda", ['player1', 'player2'])
    asyncio.get_event_loop().run_until_complete(mygame.generate_hands())
    print(True)
