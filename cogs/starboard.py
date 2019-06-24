
import discord
from discord.ext import commands
from utils import is_loud_message


class Pinboard(commands.Cog):
	''' DMs you when certain words are said in certain channels.'''

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db['starboard']


	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		if payload.emoji.id == TRIGGER_EMOJI:
			await self.add(payload.message)


	async def add(self, msg: discord.Message):
		pin_id = self.get_pin_from_msg(msg):
			if pin_id:
				self.update_pin(pin_id)
			else:
				self.create_pin_from_msg(msg)

	async def update_pin(self, pin: discord.Message):

		await self.db.update({'pin_id': pin_id}, {'$inc': {'count': 1}})

		# embed = pin.embeds[0]
		# update said embed here


	async def create_pin_from_msg(self, msg: discord.Message):

		embed = discord.Embed(description=message.content) 
		pin = await self.channel.send(embed)

		document = {'_id': msg.id, 'pin_id': pin.id, 'count': 1}
	    result = await self.db.insert_one(document)
	    print(f'{repr(result.inserted_id)}')


	async def get_pin_from_msg(self, msg: discord.Message):
		return await self.db.find({'_id': msg.id}, {'pin_id': 1 })



def setup(bot):
    bot.add_cog(Pinboard(bot))
