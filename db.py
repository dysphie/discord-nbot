from pymongo import MongoClient

db = MongoClient('localhost', 27017).get_database('rocketchat')
users = db.get_collection('users')
messages = db.get_collection('rocketchat_message')

