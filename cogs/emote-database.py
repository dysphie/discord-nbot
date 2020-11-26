# TODO: This is all terrible and written in a rush, do better?

from abc import abstractmethod, ABCMeta
from datetime import datetime
from pprint import pprint

import pymongo
from discord.ext import tasks, commands
from pymongo.errors import BulkWriteError


class EmoteAPIManager(metaclass=ABCMeta):

    @abstractmethod
    def __init__(self, session, storage):
        self.session = session
        self.storage = storage

    @abstractmethod
    async def backup_locally(self):
        pass


class BTTVManager(EmoteAPIManager):

    def __init__(self, session, storage):
        super().__init__(session, storage)

    id = "bttv"
    url = 'https://api.betterttv.net/3/emotes/shared/top'
    params = {'offset': 0, 'limit': 100}

    async def backup_locally(self):

        print(f'[{self.id}] Backing up emotes')

        # TODO: Backup in case the import fails

        try:
            deleted = await self.storage.delete_many({'source': 'bttv'})
        except Exception as e:
            print(e)
        else:
            print(f'[{self.id}] Deleted {deleted.deleted_count} existing emotes')

        for i in range(0, 200):

            emotes = []

            self.params['offset'] = i * 100
            async with self.session.get(self.url, params=self.params) as r:
                if r.status != 200:
                    raise Exception(f'[{self.id}] API responded with status {r.status}')

                data = await r.json()

                for e in data:
                    name = e['emote']['code']
                    file = e['emote']['id']

                    emote = {
                        'name': name,
                        'owner': 0,
                        'url': f'https://cdn.betterttv.net/emote/{file}/2x',
                        'source': 'bttv'
                    }

                    emotes.append(emote)

                num_inserted = 0
                try:
                    # TODO: 'ordered=False' might lead to the wrong emote being
                    #  added if a name exists twice in 'emotes', but setting it
                    #  to false halts the entire bulk write
                    result = await self.storage.insert_many(emotes, ordered=False)
                except BulkWriteError as bwe:
                    num_inserted = bwe.details['nInserted']
                else:
                    num_inserted = len(result.inserted_ids)
                finally:
                    print(f'[{self.id}] Page {i}: Inserted {num_inserted} emotes')

        print(f'[{self.id}] Finished import')


class FFZManager(EmoteAPIManager):
    id = 'ffz'
    url = 'https://api.frankerfacez.com/v1/emoticons'
    params = {
        'high_dpi': 'off',
        'sort': 'count-desc',
        'per_page': 200,
        'page': 1
    }

    def __init__(self, session, storage):
        super().__init__(session, storage)

    async def backup_locally(self):

        try:
            deleted = await self.storage.delete_many({'source': 'ffz'})
        except Exception as e:
            print(e)
        else:
            print(f'[{self.id}] Deleted {deleted.deleted_count} existing emotes')

        print(f'[{self.id}] Backing up emotes')
        await self.backup_from_page(1)
        print(f'[{self.id}] Finished import')

    async def backup_from_page(self, page_num: int):

        self.params['page'] = page_num  # Update request headers

        async with self.session.get(self.url, params=self.params) as r:
            if r.status != 200:
                raise Exception(f'[{self.id}] API responded with status {r.status}')

            data = await r.json()

            emotes = []
            for e in data['emoticons']:
                name = e['name']
                url = e['urls'].get('2') or e['urls'].get('1')

                emote = {
                    'name': name,
                    'owner': 0,
                    'url': f'https:{url}',
                    'source': 'ffz'
                }

                emotes.append(emote)

            num_inserted = 0
            try:
                # TODO: 'ordered=False' might lead to the wrong emote being
                #  added if a name exists twice in 'emotes', but setting it
                #  to false halts the entire bulk write
                result = await self.storage.insert_many(emotes, ordered=False)
            except BulkWriteError as bwe:
                num_inserted = bwe.details['nInserted']
            else:
                num_inserted = len(result.inserted_ids)
            finally:
                print(f'[{self.id}] Page {self.params["page"]}: Inserted {num_inserted} emotes')

            # Recursively fetch subsequent pages
            # if data['_pages'] > page_num:
            if page_num < 200:  # limit of 200 for now
                await self.backup_from_page(page_num + 1)


class EmoteManager(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.storage = bot.db['new_emotes']
        self.session = bot.session

        bttv = BTTVManager(self.session, self.storage)
        ffz = FFZManager(self.session, self.storage)
        self.apis = [bttv, ffz]
        self.rebuild_emotes.start()

    def cog_unload(self):
        self.rebuild_emotes.cancel()

    async def ensure_index(self):

        # TODO: The idea is to allow non-unique emote names and let queries dictate
        #  which source to prioritize, but that requires editing cogs.emoter and
        #  I don't feel like it right now, so let's just uniquely index 'name' for now
        # await self.storage.create_index([("name", pymongo.DESCENDING),
        #                                  ("source", pymongo.DESCENDING)],
        #                                 unique=True)

        await self.storage.create_index([("name", pymongo.DESCENDING)], unique=True)

    @staticmethod
    def compute_db_age(last_update):
        d = (datetime.now() - last_update).days
        return d

    @tasks.loop(hours=48)
    async def rebuild_emotes(self):

        await self.ensure_index()  # TODO: Move to init

        print('Checking if emote DB needs an update..')

        result = await self.storage.find_one({'_lastUpdated': {'$exists': 1}})

        # Rebuild DB if its non-existent or older than 2 days
        if not result or self.compute_db_age(result['_lastUpdated']) > 2:
            print("Outdated emote database detected, updating...")
            try:
                for api in self.apis:
                    await api.backup_locally()
            except Exception:
                pass
            else:
                await self.storage.update_one(
                    {'_lastUpdated': {'$exists': 1}},
                    {"$set": {'_lastUpdated': datetime.now()}},
                    upsert=True)
        else:
            print("Database was up to date, no action needed")

    @rebuild_emotes.before_loop
    async def before_cleaner(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(EmoteManager(bot))
