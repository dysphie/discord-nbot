import re
import time
import zlib
from datetime import datetime
from io import StringIO
from typing import List, Iterable

import markovify
import pymongo
from pymongo.cursor import Cursor

from db import chat, models
from logger import log

REJECT_REGEX = re.compile(r"(^')|('$)|\s'|'\s|[\"(\(\)\[\])]")
MESSAGE_URL_REGEX = re.compile(r'https?://(\S+)')


class DiscordText(markovify.NewlineText):
    # github.com/jsvine/markovify/issues/84
    def test_sentence_input(self, sentence):
        return True


def _get_model_str(qry: Cursor) -> str:
    f = StringIO()
    for msg in qry:
        message = _filter_message(msg['m'])
        if not _should_skip_message(message):
            f.write(message)
            f.write('\n')
    return f.getvalue()


def _get_model_str_from_array(messages: List[str]) -> str:
    f = StringIO()
    for msg in messages:
        message = _filter_message(msg)
        if not _should_skip_message(message):
            f.write(message)
            f.write('\n')
    return f.getvalue()


def create_model(user_id: int) -> DiscordText:
    start_time = time.time()
    log.info('Constructing speech model for %d...' % user_id)
    qry = chat.find({'a': user_id}, {'m': 1, '_id': 0})
    model = DiscordText(_get_model_str(qry))
    log.info('Created model in %.3fs.', time.time() - start_time)
    _save_model(user_id, model)
    return model


def _save_model(user_id: int, model: DiscordText):
    log.info('Compressing model...')
    compressed = zlib.compress(model.to_json().encode('utf-8'), level=9)
    log.info('Compressed model size: %s', len(compressed))
    models.update_one({'_id': user_id}, {'$set': {'model': compressed, 'date': datetime.utcnow()}}, upsert=True)


def _should_skip_message(message: str) -> bool:
    # Discard orphaned brackets and quotes
    return not message or message.startswith('.') or REJECT_REGEX.search(message)


def _filter_message(message: str) -> str:
    # Remove urls
    return re.sub(MESSAGE_URL_REGEX, '', message)


def _should_recreate_model(user_id: int, model: dict):
    qry = chat.find({'a': user_id}).sort('d', pymongo.DESCENDING).limit(1)
    try:
        newest_date = qry[0]['d']
    except IndexError:
        newest_date = datetime(2015, 1, 1)
    return newest_date > model['date']


def get_model_for_user(user_id: int) -> DiscordText:
    model = models.find_one({'_id': user_id})
    if model and _should_recreate_model(user_id, model):
        log.info('Re-creating model for %s', user_id)
        model = None
    if model:
        uncompressed_model = zlib.decompress(model['model'])
        model = DiscordText.from_json(uncompressed_model)
    else:
        model = create_model(user_id)
    return model


def get_model_for_users(user_ids: Iterable[int]) -> List[DiscordText]:
    qry = models.find({'_id': {'$in': [i for i in user_ids]}})
    db_models = {m['_id']: DiscordText.from_json(zlib.decompress(m['model'])) for m in qry}
    missing = [i for i in user_ids if i not in db_models]
    if missing:
        db_models.update({user_id: create_model(user_id) for user_id in missing})
    # Return models in the order that we received the user ids
    return [db_models[user_id] for user_id in user_ids]


def fabricate_message_from_history(messages: List[str]) -> str:
    model = DiscordText(_get_model_str_from_array(messages))
    history_count = 10000
    qry = chat.find(None, {'m': 1, '_id': 0}).sort([('d', pymongo.DESCENDING)]).limit(history_count)
    last_10k_messages_model = DiscordText(_get_model_str(qry))
    weight = history_count / (len(messages) / 10)
    combined_model = markovify.combine(models=[model, last_10k_messages_model], weights=[weight, 1])
    return combined_model.make_sentence(tries=100)
