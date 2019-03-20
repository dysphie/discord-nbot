import asyncio

import discord

from message_generator import data_collection


class Quiz(object):
    def __init__(self):
        self.ongoing = False
        self.quiz_submissions = {}

    async def start(self, ctx):
        if self.ongoing:
            return
        self.ongoing = True
        user = data_collection.get_random_user()
        fake_msg = data_collection.fabricate_sentence(user)
        username = user['username']
        await ctx.send('**Who Dis Quiz:** \n %s' % fake_msg)
        await ctx.message.add_reaction('⏳')

        await ctx.send('**Who Dis Quiz:** \n %s' % fake_msg)
        await ctx.message.clear_reactions()
        await asyncio.sleep(20)

        winners = [player for player, guess in self.quiz_submissions.items() if guess == username]

        if len(winners) > 0:
            outcome = 'Winners: %s' % (', '.join(winners))
        else:
            outcome = 'No winners'
        await ctx.send('The answer was **%s**! %s' % (username, outcome))
        self.ongoing = False
        self.quiz_submissions = {}

    def add_submission(self, author: discord.Member, message: str):
        if self.ongoing:
            user = data_collection.guess_user(message)
            if user:
                self.quiz_submissions[author.mention] = user
