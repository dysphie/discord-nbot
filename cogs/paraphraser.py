from discord.ext import commands
from nltk.corpus import wordnet as wn
from nltk import word_tokenize, pos_tag
from random import choice
from nltk.tokenize.treebank import TreebankWordDetokenizer

whitelist = ['ADJ', 'VERB', 'NOUN', 'ADV']


def paraphrase(msg: str):

    msg_tokens = pos_tag(word_tokenize(msg), tagset='universal')
    paraphrase_tokens = []
    for (token, tag) in msg_tokens:
        if tag in whitelist:
            synonym = pick_random_synonym(token, tag)
            if synonym:
                token = synonym

        paraphrase_tokens.append(token)

    return TreebankWordDetokenizer().detokenize(paraphrase_tokens)


def pick_random_synonym(word: str, tag: str):

    synonyms = []
    synsets = wn.synsets(word, pos=eval(f'wn.{tag}'))

    if synsets:
        for synset in synsets:
            for lemma in synset.lemmas():
                synonyms.append(lemma.name())

        if(synonyms):
            synonym = choice(tuple(set(synonyms)))
            return synonym.replace("_", " ")


class Paraphraser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content.startswith('$$'):
            await message.channel.send(paraphrase(message.clean_content[2:]))


def setup(bot):
    bot.add_cog(Paraphraser(bot))
