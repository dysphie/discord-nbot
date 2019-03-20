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
import argparse
import numpy as np
import logging
import random
from typing import List

from pymongo import MongoClient, database

bot = commands.Bot(command_prefix='.')

auth_token = os.getenv('DISCORD_BOT_TOKEN')

MESSAGE_BLACKLIST = ['html', 'bot c', 'botc']
WORD_BLACKLIST = ['http://', 'https://', '[ ]']
USER_BLACKLIST = []

quiz_active = False
quiz_submissions = {}

@bot.command()
async def whodis(ctx):

    global quiz_active
    if quiz_active: return
    quiz_active = True

    await ctx.message.add_reaction('⏳')
    model_user, fake_msg = fabricate_msg()
    
    await ctx.send('**Who Dis Quiz:** \n %s' % fake_msg)
    await ctx.message.clear_reactions()
    await asyncio.sleep(20)

    winners = []
    for player, guess in quiz_submissions.items():
        if guess.lower() == model_user.lower():
            winners.append(player)

    winner_count = len(winners)
    outcome = "None"
    if (winner_count > 0):
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


def get_db(host:str, port:int, database:str):
    db_client = MongoClient(host, port)
    return db_client.get_database(database)


def get_words(messages_collection: database.Collection, query_filter: dict) -> List[str]:
    unique_words = []
    query = messages_collection.find(query_filter, {'msg': 1})
    for obj in query:
        msg = obj.get('msg')
        if not msg or should_skip_message(msg):
            continue
        words = msg.split()
        if not words:
            continue
        unique_words.extend([word for word in words if should_include_word(word)])
    return unique_words


def should_skip_message(msg: str) -> bool:
    lower_msg = msg.lower()
    return any(word in lower_msg for word in MESSAGE_BLACKLIST)


def should_include_word(word: str) -> bool:
    lower_word = word.lower()
    return not any(word in lower_word for word in WORD_BLACKLIST)


def should_skip_user(user: str) -> bool:
    lower_user = user.lower()
    return any(word in lower_user for word in USER_BLACKLIST)


def make_pairs(words: List[str]):
    for i in range(len(words) - 1):
        yield words[i], words[i + 1]


def get_all_words(all_words: List[str]) -> List[str]:
    pairs = make_pairs(all_words)
    word_dict = {}

    for word_1, word_2 in pairs:
        if word_1 in word_dict:
            word_dict[word_1].append(word_2)
        else:
            word_dict[word_1] = [word_2]

    first_word = random.choice(all_words)

    while first_word.islower():
        first_word = random.choice(all_words)

    chain = [first_word]

    for i in range(80):
        last_word = chain[-1]
        if last_word in word_dict:
            chain.append(random.choice(word_dict[last_word]))
    return chain


def pick_random_user():
    candidates = []

    users = db.get_collection('users')
    query = users.find({ "name": { '$exists': True } })
    for obj in query:
        user = obj.get('username')
        if not user or should_skip_user(user):
            continue
        candidates.append(user)
   
    return np.random.choice(candidates)


def fabricate_msg():

    db = get_db('localhost', 27017, 'rocketchat')

    candidates = []
    users = db.get_collection('users')
    query = users.find({ "name": { '$exists': True } })
    for obj in query:
        user = obj.get('username')
        if not user or should_skip_user(user):
            continue
        candidates.append(user)
   
    username = random.choice(candidates)

    query_filter = {}
    if username:
        user = users.find_one({'username': username})
        if not user:
            raise Exception('User not found: %s. User the --list-users flag to list all users.' % username)
        query_filter['u._id'] = user['_id']
    messages_collection = db.get_collection('rocketchat_message')
    all_words = get_words(messages_collection, query_filter)
    words = get_all_words(all_words)
    return username, ' '.join(words)


bot.run(auth_token)

