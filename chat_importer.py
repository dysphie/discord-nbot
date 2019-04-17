from datetime import datetime
from typing import List

from discord import Message, TextChannel
from discord.ext.commands import Context
from pymongo.errors import BulkWriteError

from db import chat
from logger import log


async def start_import(ctx):
    channel = ctx.channel
    log.info('Starting import for channel %s', channel.name)
    oldest_msg = chat.find({'c': ctx.channel.id}).sort([('d', -1)]).limit(1)
    try:
        msg = oldest_msg[0]
        after = msg['d']
    except IndexError:
        after = datetime(2015, 1, 1)
    to_save = []
    count = 0
    mention = '<@!%s>' % ctx.author.id
    try:
        async for message in channel.history(limit=100000000, after=after):  # type: Message
            # Short property names so we can be cheap and run on atlas for free
            log.debug('Importing: %s: %s', message.author.name, message.content)
            to_save.append({
                '_id': message.id,
                'a': message.author.id,
                'c': message.channel.id,
                'd': message.created_at,
                'm': message.content,
            })
            if len(to_save) == 500:
                log.info('Saving %s messages', len(to_save))
                count += _insert_many(to_save)
                to_save = []
        if to_save:
            count += _insert_many(to_save)
        await ctx.send('%s Import has finished. %d messages imported.' % (mention, count))
    except BulkWriteError as e:
        log.exception(e)
        await ctx.send('%s The import is fucked: %s' % (mention, e.details))
    except Exception as e:
        await ctx.send('%s The import is fucked: %s' % (mention, e))


def _insert_many(documents: List[dict]) -> int:
    result = chat.insert_many(documents)
    return len(result.inserted_ids)
