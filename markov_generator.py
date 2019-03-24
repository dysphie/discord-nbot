import re
import time
import zlib
from datetime import datetime
from io import StringIO

import markovify
from pymongo.cursor import Cursor

from db import chat, models
from logger import log

REJECT_REGEX = re.compile(r"(^')|('$)|\s'|'\s|[\"(\(\)\[\])]")
MESSAGE_URL_REGEX = re.compile(r'https?://(\S+)')


class DiscordText(markovify.NewlineText):

    def __init__(self, *args, **kwargs):
        super(DiscordText, self).__init__(*args, **kwargs, retain_original=False)

    # github.com/jsvine/markovify/issues/84
    def test_sentence_input(self, sentence):
        return True


def _get_model_str(qry: Cursor) -> str:
    f = StringIO()
    for msg in qry:
        message = _filter_message(msg['message'])
        if not _should_skip_message(message):
            f.write(message)
            f.write('\n')
    return f.getvalue()


def create_model(user_id: int) -> DiscordText:
    start_time = time.time()
    log.info('Constructing speech model for %d...' % user_id)
    qry = chat.find({'user_id': user_id}, {'message': 1, '_id': 0})
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


def fabricate_sentence(user_id: int) -> str:
    # Get cached model or bail
    model = models.find_one({'_id': user_id})
    if model:
        uncompressed_model = zlib.decompress(model['model'])
        model = DiscordText.from_json(uncompressed_model)
    else:
        model = create_model(user_id)
    return model.make_sentence(tries=100)
