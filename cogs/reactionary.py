import os

from discord.ext import commands

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException


class Shapiro(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def shapiro(self, ctx):

        chrome_options = webdriver.ChromeOptions()
        chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        browser = webdriver.Chrome(executable_path=os.environ.get("CHROMEDRIVER_PATH"), chrome_options=chrome_options)

        browser.get("gamingclickbaitgenerator.html")
        delay = 10  # seconds
        try:
            generated = WebDriverWait(browser, delay).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div/div/p")))
            content = generated.text

        except TimeoutException:
            content = 'Failed to get content'

        browser.close()
        await ctx.send(content)


def setup(bot):
    bot.add_cog(Shapiro(bot))
