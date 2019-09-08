from discord.utils import escape_markdown as em
import re


def clean(s: str, escape_markdown=False):

    s = re.sub(r'@(everyone|here)', '@\u200b\\1', s)
    s = re.sub(r'\<.*?\>', '', s)
    s = re.sub(r'http?s\:\/\/\w+', '', s)

    if escape_markdown:
        s = em(s)

    return s.strip()
