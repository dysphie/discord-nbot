import re

MENTION_RE = re.compile(r'(<@!?[0-9]+>|@everyone|@here) ?')


def strip_mentions(msg: str):
    return MENTION_RE.sub('', msg)

