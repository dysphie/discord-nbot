import argparse
import logging
import random
from typing import List

from pymongo import MongoClient, database

MESSAGE_BLACKLIST = ['html', 'bot c', 'botc']
WORD_BLACKLIST = ['http://', 'https://', '[ ]']


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
        if not words or len(words) > 20:
            continue
        unique_words.extend([word for word in words if should_include_word(word)])
    return unique_words


def should_skip_message(msg: str) -> bool:
    lower_msg = msg.lower()
    return any(word in lower_msg for word in MESSAGE_BLACKLIST)


def should_include_word(word: str) -> bool:
    lower_word = word.lower()
    return not any(word in lower_word for word in WORD_BLACKLIST)


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

    for i in range(args.word_count):
        last_word = chain[-1]
        if last_word in word_dict:
            chain.append(random.choice(word_dict[last_word]))
    return chain


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('--db_host', type=str, default='localhost', help='Database host')
    parser.add_argument('--db_port', type=int, default=27017, help='Database port')
    parser.add_argument('--db_name', type=str, default='rocketchat', help='Database name')
    parser.add_argument('--username', type=str, help='Username to filter on')
    parser.add_argument('--room_id', type=str, default='GENERAL', help='Room from which the words should be taken from')
    parser.add_argument('--word_count', type=int, default=200, help='How long the sentence should be')

    parser.add_argument('--list_users', action='store_true')

    args = parser.parse_args()

    db = get_db(args.db_host, args.db_port, args.db_name)

    users = db.get_collection('users')
    if args.list_users:
        for u in users.find(None, {'username': 1, 'name': 1, '_id': 1}):
            print(u)
        exit(0)

    query_filter = {}
    if args.username:
        user = users.find_one({'username': args.username})
        if not user:
            raise Exception('User not found: %s. User the --list-users flag to list all users.' % args.username)
        query_filter['u._id'] = user['_id']
        if args.room_id:
            query_filter['rid'] = args.room_id
    messages_collection = db.get_collection('rocketchat_message')
    all_words = get_words(messages_collection, query_filter)
    words = get_all_words(all_words)
    print(' '.join(words))
