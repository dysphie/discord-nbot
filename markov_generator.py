import logging
import re
import time

import markovify

from db import chat, models


class DiscordText(markovify.NewlineText):

    # github.com/jsvine/markovify/issues/84
    def test_sentence_input(self, sentence):
        return True


def create_model(user_id: int):
    logging.info('Creating speech model for %d...' % user_id)

    query = chat.find({'user_id': user_id}, {'message': 1})
    # TODO: Improve this query, make it ignore null AND empty strings
    if query is None:
        logging.debug('Didnt find user')
        return None

    reject_pattern = re.compile(r"(^')|('$)|\s'|'\s|[\"(\(\)\[\])]")
    # Discard orphaned brackets and quotes

    total = query.count()
    parsed_count = 0

    # This approach is slow as shit, but generates compact models and is easy on memory
    model = None
    start_time = time.time()
    log_interval = 100
    for document in query:
        parsed_count += 1
        message = document.get('message')
        if message == '' or re.search(reject_pattern, message):
            continue

        model_chunk = DiscordText(message)
        if model:
            model = markovify.combine(models=[model, model_chunk])
        else:
            model = model_chunk
        if parsed_count % log_interval == 0:
            now = time.time()
            avg_time = (now - start_time) / log_interval
            logging.info('Processing entry %d of %d (avg %.4fs per entry)' % (parsed_count, total, avg_time))
            start_time = now

    models.insert_one({'user_id': user_id, 'model': model.to_json()})
    return model


def fabricate_sentence(user_id):
    # Get cached model or bail
    query = models.find_one({'user_id': user_id})
    if query is None:
        return

    model = DiscordText.from_json(query.get('model'))
    return model.make_sentence(tries=100)
