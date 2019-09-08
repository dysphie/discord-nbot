import asyncio
from aiohttp import ClientSession
from collections import OrderedDict
from collections import deque
from discord.ext import commands
from hashlib import md5
from urllib.parse import quote as qs
from utils import clean


class Conversation(commands.Cog, name="Conversation"):

    def __init__(self, bot):
        self.bot = bot
        self.bot.brain = Cleverbot()

    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def c(self, ctx, *, message: str):
        message = clean(message)
        if message:
            async with ctx.typing():
                response = await self.bot.brain.ask(message)
                if response:
                    response = clean(response, escape_markdown=True)
                    if response:
                        await ctx.send(response)


class CleverbotException(Exception):
    pass


class Cleverbot:
    """ Cleverbot public API Session wrapper for python """

    # constants used for interacting
    XVIS = 'TEI939AFFIAGAYQZ'
    HOST = 'https://www.cleverbot.com'
    BASE = HOST + '/webservicemin'
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

    def __init__(self, *, loop=None):
        self.prepared = False
        self.conversation = deque()
        self.params = OrderedDict()
        self.stimulus = self.session_id = ''
        self.loop = loop or asyncio.get_event_loop()
        self.session = ClientSession(loop=self.loop)
        self.params['uc'] = 'UseOfficialCleverbotAPI'
        self.headers = {
            'Origin': __class__.HOST,
            'User-Agent': __class__.UA,
            'Referer': __class__.HOST + '/',
            'Cookie': {'XVIS': __class__.XVIS}
        }

    async def close(self):
        """ Close the cleverbot http session """
        if not self.session.closed:
            await self.session.close()

    async def ask(self, question):
        """ Ask a question to the cleverbot session """
        # check if connection is open
        if self.session.closed:
            raise CleverbotException('Session is closed')

        # convert to url encoded string
        self.stimulus = qs(question)

        # modify parameters if sesison is prepared
        if self.prepared:
            self.params['in'] = self.stimulus
            self.params['ns'] = str(int(self.params['ns']) + 1)

        # perform request and initiaze if needed
        resp = await self._send()
        if len(self.params.keys()) < 2:
            self._prepare(resp)
        self.conversation.append(question)
        self.params['out'] = resp['headers']['cboutput']

        # parse the repsonse
        parsed = [line.split('\r') for line in
                  resp['data'].split('\r\r\r\r\r\r')[:-1]]
        if parsed[0][1] == 'DENIED':
            raise CleverbotException('Incorrect request authentication')
        answer = parsed[0][0]
        self.conversation.append(answer)

        # update the session information
        self.session_id = parsed[0][1]
        self.params['xai'] = '{0},{1}'.format(
            self.headers['Cookie']['XAI'], parsed[0][2])
        self.headers['Cookie']['CBSTATE'] = '&&0&&0&{0}&{1}'.format(
            self.params['ns'], '&'.join([qs(c) for c in self.conversation]))

        # return retrieved answer
        return answer

    async def _send(self):
        """ Send current conversation information and return response """
        # check if connection is open
        if self.session.closed:
            raise CleverbotException('Session is closed')

        # build conversation
        convo_str = deque()
        if len(self.conversation) > 0:
            vtext, i = 2, len(self.conversation) - 1
            while True:
                convo_str.append('vText{0}={1}'.format(vtext, qs(self.conversation[i])))
                vtext, i = vtext + 1, i - 1
                if i == 0:
                    break

        # complete conversation string
        convo_str = '&'.join(convo_str)
        if len(convo_str) > 0:
            convo_str = '&' + convo_str

        # start building the url
        session = '&sessionid=' + self.session_id if self.session_id else ''
        data = ''.join([
            'stimulus=' + self.stimulus + convo_str + '&cb_settings_language=en',
            '&cb_settings_scripting=no' + session + '&islearning=1',
            '&icognoid=wsf&icognocheck='
        ])

        # append icogcheck-hash & create params
        data += md5(data[7:33].encode()).hexdigest()
        params = '&'.join(['{0}={1}'.format(key,
                                            value if key == 'xai' else qs(value)
                                            ) for key, value in self.params.items()])

        # construct url and perform http request
        url = '{0}?{1}&'.format(__class__.BASE, params)
        headers = {'Content-Type': 'text/plain; charset=UTF-8'}
        return await self._post(url, headers=headers, data=data)

    async def _post(self, url, headers={}, data=None):
        """ HTTP Post with mini cookie-jar like middleware """
        # add default headers
        for key, value in self.headers.items():
            headers[key] = value

        # format session cookies
        headers['Cookie'] = '; '.join([
            '{0}={1}'.format(k, v) for k, v in self.headers['Cookie'].items()
        ])

        # perform request, collect cookies and return relevant information
        async with self.session.post(url, data=data, headers=headers) as resp:

            # save cookie information
            keys = [(k.lower(), k) for k in resp.headers.keys()]
            for key in keys:
                if key[0] == 'set-cookie':
                    key, value = resp.headers[key[1]].split(';')[0].split('=')
                    self.headers['Cookie'][key] = value

            # return relevant information
            has_data = len([k for k in keys if k[0] == 'content-length']) > 0
            data = await resp.text() if has_data else ''
            return {'headers': resp.headers, 'data': data}

    def _prepare(self, resp):
        """ Load initial data for session on first request """
        self.prepared = True
        self.params['out'] = ''
        self.params['in'] = ''
        self.params['bot'] = 'c'
        self.params['cbsid'] = self.session_id
        self.params['xai'] = self.headers['Cookie']['XAI']
        self.params['ns'] = '1'
        self.params['al'] = ''
        self.params['dl'] = 'en'
        self.params['flag'] = ''
        self.params['user'] = ''
        self.params['mode'] = '1'
        self.params['alt'] = '0'
        self.params['reac'] = ''
        self.params['emo'] = ''
        self.params['sou'] = 'website'
        self.params['xed'] = ''


def setup(bot):
    bot.add_cog(Conversation(bot))
