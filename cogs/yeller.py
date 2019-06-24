import discord
from discord.ext import commands
from utils import is_loud_message


class Yeller(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.shouts = bot.db['shouts']


def setup(bot):
    bot.add_cog(Yeller(bot))
