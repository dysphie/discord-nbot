import discord
from discord.ext import commands
from utils import is_hex_color_code

ROLE_PREFIX = 'Custom: '


class Colors(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.models = bot.db['model_cache']
        self.chat = bot.db['chat_archive']

    @commands.command(aliases=['hex', 'colorme'])
    async def color(self, ctx, hex_code):

        if not is_hex_color_code(hex_code):
            await ctx.send("Please enter a valid hex color (example: ff34d0)")

        # Make sure we have space
        guild = ctx.message.guild
        if not (len(guild.roles) < 250):
            await ctx.send('No slots left. Contact an admin.')
            return

        color = discord.Colour(int(hex_code, 16))
        new_role = await guild.create_role(name=ROLE_PREFIX + hex_code, color=color)
        user = ctx.message.author

        # Remove old color roles
        for role in user.roles:
            if role.name.startswith(ROLE_PREFIX):

                await user.remove_roles(role)

                # Delete role if no one else is using it
                if not len(role.members):
                    await new_role.delete()

        # Give new role
        await user.add_roles(new_role)


def setup(bot):
    bot.add_cog(Colors(bot))
