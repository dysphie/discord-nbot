import logging
from abc import abstractmethod
from datetime import datetime
from typing import TypedDict, List, Tuple, Optional, Union

from aiohttp import ClientSession
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import BulkWriteError


class DatabaseEmote(TypedDict):
    _id: str
    url: str
    src: Union[int, str]


class ApiFetcher:

    def __init__(self, uid, collection: AsyncIOMotorCollection, session: ClientSession):
        self.uid = uid
        self.collection = collection
        self.session = session

    @abstractmethod
    async def fetch(self) -> int:
        raise NotImplementedError("API fetcher must implement fetch()")

    async def save_emotes(self, database_emotes: List[DatabaseEmote]):
        num_inserted = 0
        try:
            result = await self.collection.insert_many(database_emotes, ordered=False)
        except BulkWriteError as bwe:
            num_inserted = bwe.details['nInserted']
        else:
            num_inserted = len(result.inserted_ids)
        finally:
            print(f'[{self.uid}] Inserted {num_inserted}')


class BttvFetcher(ApiFetcher):
    urls = {
        'trending': 'https://api.betterttv.net/3/emotes/shared/trending',
        'shared': 'https://api.betterttv.net/3/emotes/shared/top'
    }
    params = {'offset': 0, 'limit': 100}

    async def fetch(self) -> int:

        print(f'[{self.uid}] Beggining fetch')
        await self.collection.delete_many({'src': self.uid})

        for section, url in self.urls.items():
            for i in range(0, 200):
                self.params['offset'] = i * 100
                emotes = []
                async with self.session.get(url, params=self.params) as r:
                    data = await r.json()
                    for e in data:
                        emote = DatabaseEmote(
                            _id=e['emote']['code'],
                            url=f'https://cdn.betterttv.net/emote/{e["emote"]["id"]}/2x',
                            src=self.uid
                        )
                        emotes.append(emote)

                    if not emotes:
                        break

                    await self.save_emotes(emotes)

        new_total = await self.collection.count_documents({'src': self.uid})
        return new_total


class FfzFetcher(ApiFetcher):
    url = 'https://api.frankerfacez.com/v1/emoticons'
    params = {
        'high_dpi': 'off',
        'sort': 'count-desc',
        'per_page': 200,
        'page': 1
    }

    async def fetch(self):

        print(f'[{self.uid}] Beggining fetch')
        await self.collection.delete_many({'src': self.uid})

        while self.params['page'] <= 200:
            async with self.session.get(self.url, params=self.params) as r:
                data = await r.json()
                emotes = []
                for e in data['emoticons']:
                    emote = DatabaseEmote(
                        _id=e['name'], src=self.uid,
                        url=e['urls'].get('2') or e['urls'].get('1')
                    )
                    emotes.append(emote)
                await self.save_emotes(emotes)

            self.params['page'] += 1

        new_total = await self.collection.count_documents({'src': self.uid})
        return new_total


class EmoteCollectionUpdater(commands.Cog):

    def __init__(self, bot):
        self.session: ClientSession = bot.session
        self.emotes = bot.db['newporter.emotes']
        self.logs = bot.db['newporter.logs']

        bttv = BttvFetcher(uid=1, collection=self.emotes, session=self.session)
        ffz = FfzFetcher(uid=2, collection=self.emotes, session=self.session)
        self.apis = (bttv, ffz)

        self.check_for_updates.start()

    def cog_unload(self):
        self.check_for_updates.cancel()

    async def get_last_update_info(self) -> Tuple[Optional[datetime], Optional[bool]]:

        result = await self.logs.find_one({'_id': 'lastEmoteCollectionUpdate'})
        if result:
            return result['date'], result['success']

    @tasks.loop(hours=1)
    async def check_for_updates(self):
        logging.debug(f'Checking for emote updates..')
        last_update_time, success = await self.get_last_update_info()
        logging.debug(f'Last update: {last_update_time} (Success: {success})')
        if not success or not datetime or (datetime.now() - last_update_time).days > 2:
            await self.update()

    async def update(self):
        logging.debug('Begin emote update..')
        success = False
        try:
            for api in self.apis:
                await api.fetch()
        except Exception as e:
            logging.error('Something went wrong updating the emote collection')
        else:
            success = True

        await self.logs.update_one(
            {'_id': 'lastEmoteCollectionUpdate'},
            {'$set': {'date': datetime.now(), 'success': success}},
            upsert=True)


def setup(bot):
    # logging.getLogger().setLevel(logging.DEBUG)
    bot.add_cog(EmoteCollectionUpdater(bot))
