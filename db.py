import os

from pymongo import MongoClient

DATABASE_URI = os.environ.get('DATABASE_URI', 'mongodb://localhost:27017/')

if not DATABASE_URI:
    raise Exception('You must set the DATABASE_URI environment variable')

db = MongoClient(DATABASE_URI).get_database('test')
chat = db.get_collection('discord_chat')
models = db.get_collection('model_cache')
