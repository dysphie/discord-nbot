import discord
from discord import TextChannel
from discord.ext import commands


class Utils(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.bot_has_permissions(manage_webhooks=True)
    async def get_webhook_for_channel(self, channel: TextChannel):
        webhooks = await channel.webhooks()
        try:
            webhook = next(w for w in webhooks if w.user == self.bot.user)
        except StopIteration:
            webhook = await channel.create_webhook(name='NBot')

        return webhook


def truncate_string(s: str, maxlen: int, suffix='..'):
    return s[:maxlen - len(suffix)] + suffix if len(s) > maxlen else s


def lazyfind_user(guild: discord.Guild, name: str):
    for member in guild.members:
        if name == member.id:
            return member
        for alias in [member.name, member.display_name]:
            if name.lower() in alias.lower():
                return member


def setup(bot):
    bot.add_cog(Utils(bot))