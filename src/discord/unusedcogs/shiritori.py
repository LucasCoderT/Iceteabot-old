import discord
from discord.ext import commands


class Shiritori:
    def __init__(self, bot):
        self.bot = bot
        self.gameroom = discord.Object("221070540905906186")

    @commands.command(pass_context=True)
    async def Shiritori(self, ctx):
        if await rolecall(ctx.message.author.id, 'moderator'):
            await self.bot.send_message(self.gameroom, "{} has opened a game of ``Shiritori``!!\n "
                                                       "```js\n"
                                                       "Rules:\n"
                                                       ""
                                                       "use !aschente to join ")
            self.aschente.enabled = True

    @commands.command(pass_context=True, enabled=False)
    async def aschente(self, ctx):


def setup(bot):
    bot.add_cog(Shiritori(bot))
