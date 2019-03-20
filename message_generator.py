import random
from typing import List

from db import users, messages


class DataCollection(object):  # shitty name
    MESSAGE_BLACKLIST = ['html', 'bot c', 'botc']
    WORD_BLACKLIST = ['http://', 'https://', '[', ']']
    USER_BLACKLIST = [None, 'kanqaroo', 'Olex', 'rocket.cat', 'bot', 'AmhpLiFy', 'Z',
                      'WCEendT', 'Foofoo14', 'Glass', 'testaccount', 'jack.lupino', 'SylphCA',
                      'jorainbo', 'x00irt', 'slamarechi', 'tadiconedr', 'Z', 'Bowser',
                      'el_frotal', 'Conifacio', 'Uwaai', 'Reign', '-_-BIER--_--', 'Nicarasu']

    def __init__(self):
        self.candidates = self._get_candidates()
        self.aliases = self._build_aliases(self.candidates)

    def get_random_user(self):
        return random.choice(self.candidates)

    def fabricate_sentence(self, user: dict) -> str:
        query_filter = {'u._id': user['_id']}
        all_words = self._get_words(query_filter)
        words = self._get_all_words(all_words)
        return ' '.join(words)

    def guess_user(self, query: str):
        if len(query) < 3:
            return None
        query = query.lower().strip()
        for alias in self.aliases:
            if query in alias:
                return self.aliases[alias]

    def _get_words(self, query_filter: dict) -> List[str]:
        unique_words = []
        # TODO: cache per user
        query = messages.find(query_filter, {'msg': 1})
        for obj in query:
            msg = obj.get('msg')
            if not msg or self._should_skip_message(msg):
                continue
            words = msg.split()
            if not words or len(words) > 20:
                continue
            unique_words.extend([word for word in words if self._should_include_word(word)])
        return unique_words

    def _get_all_words(self, all_words: List[str]) -> List[str]:
        pairs = self._make_pairs(all_words)
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

        for i in range(80):
            last_word = chain[-1]
            if last_word in word_dict:
                chain.append(random.choice(word_dict[last_word]))
        return chain

    def _should_skip_message(self, msg: str) -> bool:
        lower_msg = msg.lower()
        return any(word in lower_msg for word in self.MESSAGE_BLACKLIST)

    def _should_include_word(self, word: str) -> bool:
        lower_word = word.lower()
        return not any(word in lower_word for word in self.WORD_BLACKLIST)

    def _should_skip_user(self, user: str) -> bool:
        return any(username == user for username in self.USER_BLACKLIST)

    def _make_pairs(self, words: List[str]):
        for i in range(len(words) - 1):
            yield words[i], words[i + 1]

    def _get_candidates(self):
        query = users.find({"name": {'$exists': True}})
        return [obj for obj in query if not self._should_skip_user(obj.get('username'))]

    def _build_aliases(self, candidates: List[dict]):
        aliases = {}
        # TODO: include old usernames (Q == Nayncore == dysphy... etc)
        for candidate in candidates:
            username = candidate['username']
            aliases[username.lower()] = username
        return aliases


data_collection = DataCollection()
