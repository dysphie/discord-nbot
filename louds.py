import re
import string

import hashlib
from discord import Message
from pymongo.errors import DuplicateKeyError

from db import yells, chat
from util import strip_mentions

WORD_SPLIT_RE = re.compile(r'\s+')
ALL_LETTERS = string.ascii_uppercase + ' '


async def handle_loud_message(message: Message):
    msg = strip_mentions(message.content)
    if is_loud_message(msg):
        _save_loud_message(msg)
        cursor = yells.aggregate([{'$sample': {'size': 1}}])
        for dic in cursor:
            await message.channel.send(dic.get('m'))
            break


def is_loud_message(message: str):
    # louds must be:
    #  * uppercase (duh)
    #  * eight or more letters
    #  * at least 90% letters (not counting whitespace)
    #  * two or more words
    is_uppercase = message == message.upper() and message != message.lower()
    if not is_uppercase:
        return False
    # Strip emojis and whatnot for counting characters
    total_character_count = sum(1 for letter in message if letter in ALL_LETTERS)
    letter_count = len(WORD_SPLIT_RE.sub('', message))
    ratio = total_character_count / letter_count
    whitespace_count = len(WORD_SPLIT_RE.findall(message))
    return total_character_count >= 8 and ratio >= 0.9 and whitespace_count >= 1


def import_loud_messages():
    yells.delete_many({})
    unique_messages = list(set(_get_loud_messages()))
    for chunk in chunks(unique_messages, 1000):
        yells.insert_many([_get_loud_model(message) for message in chunk], ordered=False)
    return len(unique_messages)


def _get_loud_messages():
    for message in chat.find({}, {'m'}):
        if is_loud_message(message['m']):
            yield strip_mentions(message['m'])


def _save_loud_message(message: str):
    try:
        yells.insert_one(_get_loud_model(message))
    except DuplicateKeyError:
        pass


def _get_loud_model(message: str):
    return {'_id': hashlib.sha256(message.encode('utf-8')).hexdigest(), 'm': message}


def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]
