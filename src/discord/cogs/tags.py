import random
import typing
from collections import Counter
from difflib import SequenceMatcher

from src.discord.utils.nextgen import Tag
from src.discord.utils.paginator import TagPaginator
from src.discord.utils.permissions import *


# TODO create shadow user to own all orphaned tags
# TODO Need to find a way to change a row's id. I think this is possible...?


class Tags:
    def __init__(self, bot):
        self.bot = bot
        self.medals = ["\U0001f947", "\U0001F948", "\U0001F949"]

    def __str__(self):
        return self.__class__.__name__

    async def __local_check(self, ctx):
        return ctx.guild is not None

    async def __error(self, ctx, error):
        if isinstance(error, TagNotFound):
            # response_list = await self.search_tags(ctx, error.param)
            # if len(response_list) > 0:
            #     response_message = "\n".join([row.id for row in response_list])
            #     await ctx.send(f"Tag **{error.param}** not found\ninstead found these tags:\n\n{response_message}")
            await ctx.send(f"Tag ``{error.param}`` Not Found")
        elif isinstance(error, TagAlreadyExists):
            await ctx.send(f"``{error.param}`` already exists")
        else:
            await ctx.send(f"```\n{error}\n```", delete_after=20)

    @staticmethod
    def clean_tag_content(content):
        return content.replace('@everyone', '@\u200beveryone').replace('@here', '@\u200bhere')

    def get_tags_by_member(self, ctx, member) -> typing.List[Tag]:
        """Cache lookup"""
        return sorted([tag for tag in ctx.guild_data.tags.values() if tag.author == member.id],
                      key=lambda tag: tag.count, reverse=True)

    def top_tag_creators(self, ctx):
        data = Counter()
        for tag in ctx.guild_data.tags.values():
            data[tag.author] += 1
        return data

    async def get_top_tag_users(self, ctx):
        """Tag Board calls"""
        payload = await self.bot.fetch_data(f"guilds/{ctx.guild.id}/tagboard")
        return payload

    async def guild_tag_stats(self, ctx):
        """Cache lookup"""
        if not len(ctx.guild_data.tags) >= 3:
            return await ctx.send("This guild does not have enough data for this command")
        embed = discord.Embed(colour=discord.Colour.blurple(), title=f"{ctx.guild.name} Stats")
        embed.set_footer(text="These statistics are server-specific")
        guild_tags = ctx.guild_data.tags
        embed.description = f"{len(guild_tags)} tags, {sum([tag.count for tag in guild_tags.values()])} Tag Uses"
        top_tags = sorted(guild_tags.values(), key=lambda tag: tag.count, reverse=True)
        top_tag_users = await self.get_top_tag_users(ctx)
        data = {}
        for member, calls in top_tag_users.items():
            data[member] = sum(calls.values())
        top_tag_users = data
        top_tag_creators = self.top_tag_creators(ctx)
        top_three_tags = ["{0} : {1} ({2} uses)".format(medal, tag, tag.count) for medal, tag in
                          zip(self.medals, top_tags)]
        top_three_users = [
            "{0} : {1} ({2} times)".format(medal, ctx.guild.get_member(int(user)).mention, top_tag_users[user]) for
            medal, user in zip(self.medals, top_tag_users)]
        top_three_creators = [
            "{0} : {1} ({2} tags)".format(medal, ctx.guild.get_member(int(user)).mention, top_tag_creators[user]) for
            medal, user in zip(self.medals, top_tag_creators)
        ]
        embed.add_field(name="Top Tags", value="\n".join(top_three_tags), inline=False)
        embed.add_field(name="Top Tag Users", value="\n".join(top_three_users), inline=False)
        embed.add_field(name="Top Tag Creators", value="\n".join(top_three_creators), inline=False)
        return await ctx.send(embed=embed)

    async def member_tag_stats(self, ctx, member):
        """Cache Lookup"""
        tags = self.get_tags_by_member(ctx, member)
        data = await self.get_top_tag_users(ctx)
        data = data[str(member.id)]
        embed = discord.Embed(colour=discord.Colour.blurple())
        embed.set_footer(text='These statistics are server-specific.')
        embed.set_author(name=member.display_name, icon_url=member.avatar_url)
        embed.add_field(name="Owned Tags", value=str(len(tags)))
        embed.add_field(name="Owned Tag Uses", value=str(sum(tag.count for tag in tags if tag.title in data)))
        embed.add_field(name="Tag Command Uses", value=str(sum(data.values())))
        for medal, tag in zip(self.medals, tags):
            embed.add_field(name=f"{medal} Owned Tag", value=f"{tag} ({tag.count} Uses)")
        return await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, tag_name: str):
        """Returns an existing tag"""
        tag, alias = await ctx.guild_data.call_tag(ctx, tag_name)
        if tag:
            await ctx.send(tag.content)

    @tag.command(aliases=['add'])
    async def create(self, ctx, name: str, *, content: str):
        """Creates a tag"""
        content = self.clean_tag_content(content)
        response = await ctx.guild_data.create_tag(content, name, ctx.author.id)
        if response:
            await ctx.send("Tag successfully created")
        else:
            await ctx.send("Uh oh, something went wrong")

    @tag.command()
    async def edit(self, ctx, name: str, *, new_content: str):
        """Edit a tag's content"""
        tag, alias = ctx.guild_data.get_tag(name)
        if alias:
            return await ctx.send("Unable to edit alias")
        if tag.author == ctx.author.id:
            content = self.clean_tag_content(new_content)
            await ctx.guild_data.edit_tag(tag.title, content)
            await ctx.send("Tag updated Successfully")

    @tag.command()
    async def info(self, ctx, *, name: str):
        """Displays information on a specific tag"""
        tag, alias = ctx.guild_data.get_tag(name)

        if alias is None:
            embed = discord.Embed(description=f"{ctx.message.guild.name} ``{tag.title}`` tag information")
            user = ctx.guild.get_member(tag.author)
            embed.set_author(name=user.display_name, icon_url=user.avatar_url)
            embed.add_field(name="Tag name", value=tag.title)
            embed.add_field(name="Amount used", value=tag.count)
            embed.timestamp = tag.created
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=f"{ctx.message.guild.name} ``{alias.title}`` alias information")
            user = ctx.guild.get_member(alias.author)
            embed.add_field(name="Author", value=user or "Unknown")
            embed.add_field(name="Amount used", value=alias.count)
            embed.timestamp = alias.created
            await ctx.send(embed=embed)

    @tag.command()
    async def delete(self, ctx, *, name: str):
        """Deletes a tag, only an administrator or tag owner may delete tags"""
        tag, alias = ctx.guild_data.get_tag(name)
        if alias is not None:
            if ctx.author.guild_permissions.administrator or alias.author == ctx.author.id:
                response = await ctx.guild_data.delete_alias(alias)
                if response:
                    await ctx.send("aliases deleted")
                else:
                    await ctx.send("Alias unsuccessfully deleted")
        else:
            if ctx.author.guild_permissions.administrator or tag.author == ctx.author.id:
                response = await ctx.guild_data.delete_tag(tag)
                if response:
                    await ctx.send("Tag and all aliases deleted")
                else:
                    await ctx.send("Tag unsuccessfully deleted")

    @tag.command()
    async def alias(self, ctx, name: str, *, new_alias: str):
        """Adds an alias to a tag, allows it to be called by other names"""
        ctx.guild_data.get_tag(name)
        await ctx.guild_data.create_alias(name, new_alias, ctx.author.id)
        await ctx.send(":thumbsup:")

    async def search_tags(self, ctx, query):

        guild_tags = ctx.guild_data.tags
        response_list = []
        for tag in guild_tags:
            match_percent = SequenceMatcher(None, tag.title, query).ratio()
            if match_percent >= 3.0:
                continue
            if match_percent > .60:
                response_list.append(tag)
        return response_list

    @tag.command()
    async def stats(self, ctx, user: discord.Member = None):
        """Display either the servers's or the user's stats"""
        if user is None:
            await self.guild_tag_stats(ctx)
        else:
            await self.member_tag_stats(ctx, user)

    @tag.command(enabled=False)
    async def claim(self, ctx, otag: str):
        """Claims an orphaned tag"""
        tag, alias = ctx.guild_data.get_tag(otag)

        if otag.orphaned:
            otag.author = str(ctx.author.id)
            otag.orphaned = False
            await otag.save()
            await ctx.send(f"You have sucessfully claimed {otag.id}")
        else:
            await ctx.send("This tag already has an owner")

    @tag.command(enabled=False)
    async def orphan(self, ctx, otag: str):
        """Allows a user to unclaim a tag, used for trading tags?"""
        tag, alias = ctx.guild_data.get_tag(otag)

        if not otag.orphaned:
            otag.orphaned = True
            otag.author = "00000000000000000000"
            await otag.save()
            await ctx.send("You no longer own this tag and can be claimed by anyone")
        else:
            await ctx.send("You do not own this tag")

    @tag.command()
    async def search(self, ctx, *, query):
        """Searches for similar tags based on query

        eg: tag search dog

        found tags:
        dog
        dogs
        doggo

        """
        response_list = await self.search_tags(ctx, query)
        if len(response_list) > 0:
            response_message = "\n".join([r.id for r in response_list[:3]])
            await ctx.send(f"Found these tags:\n{response_message}")
        else:
            await ctx.send("No similar tags found")

    @tag.command()
    async def random(self, ctx):
        """Retrieves a random tag from the database"""
        random_tag = random.choice(ctx.guild_data.tags)
        if random_tag is None:
            return await ctx.send("Unable to find any tags")
        await ctx.send(await ctx.guild_data.call_tag(ctx, random_tag))

    @tag.command(name="list")
    async def _list(self, ctx, target: discord.Member = None):
        """Display's a list of all tags owned by the mentioned user or if no one mentioned then authors"""
        target = target or ctx.author
        tags = await ctx.guild_data.get_member_tags(target.id)
        paginator = TagPaginator(ctx, entries=[tag for tag in tags])
        await paginator.paginate()


def setup(bot):
    bot.add_cog(Tags(bot))
