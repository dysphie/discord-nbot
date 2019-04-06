import os

from pymongo import MongoClient

DATABASE_URI = os.environ.get('DATABASE_URI', 'mongodb://localhost:27017/')
DB_NAME = os.environ.get('DATABASE_NAME', 'test')

if not DATABASE_URI:
    raise Exception('You must set the DATABASE_URI environment variable')

db = MongoClient(DATABASE_URI).get_database(DB_NAME)
chat = db.get_collection('chat_archive')
models = db.get_collection('model_cache')
webhooks = db.get_collection('webhooks')
