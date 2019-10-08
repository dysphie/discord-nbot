import discord


# TODO:
#   Combine alerts into alert(ctx, AlertType, msg)
#   Proper escaping of {content}

def create_human_list(words: list):
    words = [f'`{word}`' for word in words]
    human_list = ", ".join(words[:-2] + [" and ".join(words[-2:])])
    return human_list


async def send_warning(ctx: discord.abc.Messageable, content: str):
    color = discord.Color(0xffcb05)
    prefix = '<:warn:631111392321339412>'
    embed = discord.Embed(color=color, description=f'{prefix} **{content}**')
    await ctx.send(embed=embed)


async def send_info(ctx: discord.abc.Messageable, content: str):
    color = discord.Color(0x41c8f5)
    prefix = '<:info:631111392237322242>'
    embed = discord.Embed(color=color, description=f'{prefix} **{content}**')
    await ctx.send(embed=embed)


async def send_success(ctx: discord.abc.Messageable, content: str):
    color = discord.Color(0x8cc63e)
    prefix = '<:success:631111392048447499>'
    embed = discord.Embed(color=color, description=f'{prefix} **{content}**')
    await ctx.send(embed=embed)


async def send_error(ctx: discord.abc.Messageable, content: str):
    color = discord.Color(0xf05840)
    prefix = '<:error:631111392400900096>'
    embed = discord.Embed(color=color, description=f'{prefix} **{content}**')
    await ctx.send(embed=embed)
