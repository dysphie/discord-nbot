import discord
from discord.ext import commands
from pymongo import MongoClient
import markovify
import re
import os

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DATABASE_URI = os.getenv('DATABASE_URI') # mongodb://localhost:27017/

if not BOT_TOKEN:
    raise Exception('You must set the DISCORD_BOT_TOKEN environment variable')

if not DATABASE_URI:
    raise Exception('You must set the DATABASE_URI environment variable')      

bot = commands.Bot(command_prefix='.')

@bot.event
async def on_ready():
    print('Ready')

db = MongoClient(DATABASE_URI)['nbot_brain']
chat = db['discord_chat']
models = db['model_cache']


class DiscordText(markovify.NewlineText):

    # github.com/jsvine/markovify/issues/84
    def test_sentence_input(self, sentence):
        return True


def create_model(user_id):

    print('Creating speech model for %d...' % user_id)

    query = chat.find({'user_id': user_id}, {'message': 1})
    # TODO: Improve this query, make it ignore null AND empty strings

    if query is None:
        print('Didnt find user')
        return None

    reject_pattern = re.compile(r"(^')|('$)|\s'|'\s|[\"(\(\)\[\])]") 
    # Discard orphaned brackets and quotes

    total = query.count()
    parsed = 0

    # This approach is slow as shit, but generates compact models and is easy on memory
    model = None
    for document in query:
        parsed += 1
        print('Processing entry %d of %d' % (parsed, total))
        message = document.get('message')
        if message == '' or re.search(reject_pattern, message): continue

        model_chunk = DiscordText(message)
        if model:
            model = markovify.combine(models=[model, model_chunk])
        else:
            model = model_chunk
        
    return model


def fabricate_sentence(user_id):

    # Get cached model or bail
    query = models.find_one({'user_id': user_id})
    if query is None: return
        
    model = DiscordText.from_json(query.get('model')) 
    return model.make_sentence(tries=100)

    
@bot.command()
async def be(ctx, *args):

    guild = ctx.channel.guild
    nickname = ' '.join(args)

    user = guild.get_member_named(nickname)
    if not user: return

    content = fabricate_sentence(user.id)

    webhook = await ctx.channel.create_webhook(name='Temporary')
    await webhook.send(content=content, username=nickname, avatar_url=user.avatar_url)
    await webhook.delete()


@bot.command()
async def add(ctx, user_id: int):

    model = create_model(user_id)
    models.insert_one({'user_id': user_id, 'model': model.to_json()})

    for i in range(5):
        print('TEST SENTENCE: ' + model.make_sentence(tries=100))


bot.run(BOT_TOKEN)