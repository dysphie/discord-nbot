import os

from discord.ext import commands

from quiz import Quiz

bot = commands.Bot(command_prefix='.')


@bot.command()
async def whodis(ctx):
    await quiz.start(ctx)


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    quiz.add_submission(message.author, message.content)


if __name__ == '__main__':
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not BOT_TOKEN:
        raise Exception('You must set the DISCORD_BOT_TOKEN environment variable')

    quiz = Quiz()
    if BOT_TOKEN != 'debug':
        bot.run(BOT_TOKEN)
