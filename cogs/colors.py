import re
import discord
from discord import Option, slash_command, ApplicationContext, Member
from discord.ext import commands


def is_hex_color_code(s: str):
    return bool(re.match('[a-fA-F0-9]{6}$', s))


class Colors(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="namecolor", description='Sets your name color')
    async def color(self,
                    ctx: ApplicationContext,
                    hex_code: Option(str, "Hex code")):

        if not is_hex_color_code(hex_code):
            await ctx.respond("Invalid hex code. Color format example: 44ff00`")

        # Make sure we have guild space
        if not (len(ctx.guild.roles) < 250):
            await ctx.respond('No custom role slots left!')
            return

        prefix = self.bot.cfg['color-role-prefix']

        color = discord.Colour(int(hex_code, 16))
        new_role = await ctx.guild.create_role(name=f'{prefix} #{hex_code}', color=color)

        user: Member = ctx.author

        # Unequip old colors
        for role in ctx.user.roles:
            if role.name.startswith(prefix):
                await user.remove_roles(role)

                # Delete if we're the last owner
                if len(role.members) < 2:
                    await role.delete()

        # Give new color
        try:
            await user.add_roles(new_role)
        except Exception as e:
            await ctx.respond(f'Failed to assign new color: {e}')
        else:
            await ctx.respond("✅")


def setup(bot):
    bot.add_cog(Colors(bot))
