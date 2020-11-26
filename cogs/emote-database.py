from abc import abstractmethod, ABCMeta

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

    url = 'https://api.betterttv.net/3/emotes/shared/top'
    params = {'offset': 0, 'limit': 100}

    async def backup_locally(self):

        print('Backing up BTTV emotes')

        # TODO: Backup in case the import fails
        await self.storage.delete_many({'source': 'bttv'})

        emotes = []

        for i in range(0, 200):
            self.params['offset'] = i*100
            async with self.session.get(self.url, params=self.params) as r:
                if r.status == 200:
                    data = await r.json()

            # for e in data:
            #     name = e['emote']['code']
            #     file = e['emote']['id']
            #
            #     emotes.append({
            #         'name': name,
            #         'owner': 0,
            #         'url': f'https://cdn.betterttv.net/emote/{file}/2x',
            #         'source': 'bttv'
            #     })
            #
            # try:
            #     result = self.storage.insert_many(emotes, ordered=False)
            #     # TODO: 'ordered=False' might lead to the wrong emote being
            #     #  added if a name exists twice in 'emotes'
            # except BulkWriteError:
            #     pass
            # else:
            #     print(f'Inserted {len(result.inserted_ids)} from page {i}')

        print('Finished BTTV import')


class FFZManager(EmoteAPIManager):

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

        print('Backing up FFZ emotes')
        # TODO: Backup in case the import fails
        await self.storage.delete_many({'source': 'ffz'})

        pages_left = True
        self.params['page'] = 1
        while pages_left:

            async with self.session.get(self.url, params=self.params) as r:
                if r.status != 200:
                    data = await r.json()
                    raise Exception(f'non-200 API response {data}')

            data = await r.json()

            emotes = []
            for e in data['emoticons']:
                name = e['name']
                url = e['urls'].get('2') or e['urls'].get('1')

                emotes.append({
                    'name': name,
                    'owner': 0,
                    'url': f'https:{url}',
                    'source': 'ffz'
                })

            try:
                result = await self.storage.insert_many(emotes, ordered=False)
                # TODO: 'ordered=False' might lead to the wrong emote being
                #  added if a name exists twice in 'emotes'
            except BulkWriteError:
                pass
            else:
                print(f'Inserted {len(result.inserted_ids)} from page {self.params["page"]}')

            self.params['page'] += 1
            pages_left = data['_pages'] > self.params['page']


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

    @tasks.loop(seconds=199999999999)
    async def rebuild_emotes(self):
        print("Rebuilding emote database")

        await self.storage.create_index(
            [("name", pymongo.TEXT), ("source", pymongo.TEXT)], unique=True)

        await self.apis[1].backup_locally()
        # for api in self.apis:
        #    await api.backup_locally()

    @rebuild_emotes.before_loop
    async def before_cleaner(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(EmoteManager(bot))
