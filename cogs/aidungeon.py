from os import environ

from discord import TextChannel
from discord.ext import commands

import asyncio

from gql import Client, gql
from gql.transport.websockets import WebsocketsTransport


class DungeonAPI(commands.Cog):
    url = 'wss://api.aidungeon.io/subscriptions'

    def __init__(self, bot):
        self.bot = bot
        self.subscriptions = None
        self.mutations = None
        self.token = None
        self.task = None
        self.task_adventure_id = None
        self.last_message = None

    @commands.Cog.listener()
    async def on_ready(self):
        await self.authenticate(environ['DUNGEONAI_USER'], environ['DUNGEONAI_PASSWORD'])

    async def authenticate(self, username, password):

        temp_client = Client(
            transport=WebsocketsTransport(
                url=self.url
            )
        )

        query = gql(
            """
            mutation ($identifier: String, $password: String) {
              login(identifier: $identifier, password: $password) {
                accessToken
              }
            }
            """
        )

        variables = {
            'identifier': username,
            'password': password
        }

        result = await temp_client.execute_async(query, variable_values=variables)
        access_token = result['login']['accessToken']

        self.subscriptions = Client(transport=WebsocketsTransport(
            url=self.url,
            init_payload={'token': access_token})
        )
        self.mutations = Client(transport=WebsocketsTransport(
            url=self.url,
            init_payload={'token': access_token})
        )

    async def create_custom_adventure(self):
        print('DungeonAPI.create_custom_adventure()')
        query = gql(
            """
            mutation ($scenarioId: String, $prompt: String, $memory: String) {
              addAdventure(scenarioId: $scenarioId, prompt: $prompt, memory: $memory) {
                publicId
                id
              }
            }
            """
        )
        variables = {"scenarioId": "458625"}
        result = await self.mutations.execute_async(query, variable_values=variables)
        return result['addAdventure']['publicId'], result['addAdventure']['id']

    async def subscribe_task(self, adventure_id, channel):

        print('DungeonAPI.subscribe_to_adventure()')
        query = gql(
            """
            subscription ($adventureId: String) {
                actionAdded(adventureId: $adventureId) {
                  text
                  type
                }
            }
            """
        )

        variables = {'adventureId': adventure_id}
        async for result in self.subscriptions.subscribe_async(query, variables):
            # print

            new_text = result['actionAdded']['text']
            if not self.last_message:
                message = await channel.send(new_text)
                self.last_message = message
            else:
                await self.last_message.edit(content=self.last_message.content + new_text)

    async def subscribe_to_adventure(self, short_id, public_id, channel: TextChannel):

        if self.task is not None:
            print('A subscription is already active, so shutting that down')
            self.task.cancel()

        self.task = asyncio.create_task(self.subscribe_task(short_id, channel))
        self.task_adventure_id = public_id

    async def add_action(self, adventure_id, action_type, text):

        self.last_message = None

        print('add_action')
        query = gql(
            """
            mutation ($input: ActionInput) {
              addAction(input: $input) {
                message
                time
                hasBannedWord
                returnedInput
              }
            }
            """

        )

        variables = {
            "input": {
                "publicId": adventure_id,
                "type": action_type
            }
        }

        if text:
            variables["input"]["text"] = text

        await self.mutations.execute_async(query, variable_values=variables)

    @commands.command()
    async def prompt(self, ctx, *, story_pitch):
        public_id, short_id = await self.create_custom_adventure()
        print(public_id, short_id)
        await self.subscribe_to_adventure(short_id, public_id, ctx.message.channel)
        await asyncio.sleep(0.2)  # TODO: This is dumb, how do we tell when the subscription was set up?
        await self.add_action(public_id, 'story', story_pitch)

    @commands.command()
    async def do(self, ctx, *, story_pitch):

        if not self.task:
            await ctx.error('use .prompt first')

        await self.add_action(self.task_adventure_id, 'do', story_pitch)

    @commands.command()
    async def story(self, ctx, *, story_pitch):

        if not self.task:
            await ctx.error('use .prompt first')

        await self.add_action(self.task_adventure_id, 'story', story_pitch)

    @commands.command()
    async def say(self, ctx, *, story_pitch):

        if not self.task:
            await ctx.error('use .prompt first')

        await self.add_action(self.task_adventure_id, 'say', story_pitch)


def setup(bot):
    bot.add_cog(DungeonAPI(bot))
