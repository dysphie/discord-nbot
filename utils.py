from discord.utils import escape_markdown as em
import re


def clean(s: str, escape_markdown=False):

    s = re.sub(r'@(everyone|here)', '@\u200b\\1', s)
    s = re.sub(r'\<.*?\>', '', s)
    s = re.sub(r'http?s\:\/\/\w+', '', s)

    if escape_markdown:
        s = em(s)

    return s.strip()


def is_hex_color_code(s: str):
    return bool(re.match('[a-fA-F0-9]{6}$', s))


def is_loud_message(message: str):
    alph = list(filter(str.isalpha, message))
    percentage = sum(map(str.isupper, alph)) / len(alph)
    return (percentage > 0.85 and len(message.split()) > 3)
