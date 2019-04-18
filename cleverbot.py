from selenium import webdriver
import json
import time


class Cleverbot(object):
    _last_message = ''

    def __init__(self):
        self.driver = webdriver.Chrome()
        self.driver.get('http://www.cleverbot.com')

    def get_message(self):
        current_message = self._last_message
        while current_message == self._last_message:
            time.sleep(.1)
            current_message = self.driver.execute_script('return cleverbot.reply')
        self._last_message = current_message
        return current_message

    def send(self, message):
        message = json.dumps({'msg': message})
        return self.driver.execute_script("const msg = %s;cleverbot.sendAI(msg.msg)" % message)
