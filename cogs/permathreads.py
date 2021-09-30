import discord
from discord import slash_command, Option, ApplicationContext, ChannelType, TextChannel, Thread
from discord.ext import commands
from pymongo.collection import Collection

from main import DiscordBot


class Permathreads(commands.Cog):
    def __init__(self, bot):
        self.bot: DiscordBot = bot
        self.permathreads: Collection = self.bot.db['permathreads']

    @slash_command(name="permathread", description="Creates a thread that never expires")
    async def permathread(self, ctx: ApplicationContext, name: Option(str, "Thread name")):
        if not isinstance(ctx.channel, TextChannel):
            await ctx.respond('Must be inside a text channel')
            return

        thread: Thread = await ctx.channel.create_thread(name=name, type=ChannelType.public_thread)
        await self.permathreads.insert_one({'_id': thread.id})
        await ctx.respond('Created permathread')

    @commands.Cog.listener()
    async def on_ready(self):
        async for doc in self.permathreads.find({}):
            thread = await self.bot.fetch_channel(doc['_id'])
            if isinstance(thread, discord.Thread) and thread.archived:
                await thread.edit(archived=False)

    @commands.Cog.listener()
    @commands.bot_has_permissions(manage_threads=True)
    async def on_thread_join(self, thread):  # this fires for thread creation as well
        await thread.join()

    @commands.Cog.listener()
    @commands.bot_has_permissions(manage_threads=True)
    async def on_thread_update(self, old_thread, new_thread: discord.Thread):
        if new_thread.archived:
            doc = await self.permathreads.find_one({'_id': new_thread.id})
            if doc:
                await new_thread.edit(archived=False)


def setup(bot):
    bot.add_cog(Permathreads(bot))
