'''
TODO:
- Make fancy
- Implement pick_random_user() and fabricate_msg()
- Implement lenient matches for usernames (e.g. Cat/Akeno/Rossweisse)
- Maybe turn quiz into class

'''

import discord
import asyncio
import os
from discord.ext import commands

bot = commands.Bot(command_prefix='.')

auth_token = os.getenv('DISCORD_BOT_TOKEN')

quiz_active = False
quiz_submissions = {}

@bot.command()
async def whodis(ctx):

    global quiz_active
    if quiz_active: return
    quiz_active = True

    await ctx.message.add_reaction('⏳')
    model_user = pick_random_user()
    fake_msg = fabricate_msg(model_user)
    
    await ctx.send('**Who Dis Quiz:** \n %s' % fake_msg)
    await ctx.message.clear_reactions()
    await asyncio.sleep(15)

    winners = []
    for player, guess in quiz_submissions.items():
        if guess == model_user:
            winners.append(player)

    winner_count = len(winners)
    outcome = "None"
    if winner_count:
        outcome = winners[0] if winner_count == 1 else ', '.join(winners[:-1]) + ", and " + winners[-1]

    await ctx.send('The answer was **%s**! Winners: %s' % (model_user, outcome))
    quiz_active = False

@bot.event
async def on_message(message):

    await bot.process_commands(message)
    if quiz_active:
        author = message.author
        if author not in quiz_submissions.keys():
            quiz_submissions[author.mention] = message.content

def fabricate_msg(username):
    # TODO
    return 'Lorem ipsum dolor sit amet'

def pick_random_user():
    # TODO
    return 'Q'

bot.run(auth_token)