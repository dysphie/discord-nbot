from discord.ext import commands


class Admin(commands.Cog):
    """Admin-only commands that make the bot dynamic."""

    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.command(hidden=True)
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            self.bot.load_extension(module)
        except Exception as e:
            await ctx.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.has_permissions(administrator=True)
    @commands.command(hidden=True)
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        try:
            self.bot.unload_extension(module)
        except Exception as e:
            await ctx.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.add_reaction("✅")

    @commands.has_permissions(administrator=True)
    @commands.group(name='reload', hidden=True)
    async def reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            self.bot.reload_extension(module)
        except Exception as e:
            await ctx.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.add_reaction("✅")


def setup(bot):
    bot.add_cog(Admin(bot))
