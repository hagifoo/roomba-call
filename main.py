# coding: UTF-8
import base64
from google.appengine.api.app_identity.app_identity import get_application_id
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from googleapiclient.discovery import build
import json
import logging
from oauth2client.client import GoogleCredentials
import random
import webapp2


# Global Variables
credentials = GoogleCredentials.get_application_default()


# Implementations
class MainPage(webapp2.RequestHandler):
    def get(self):
        data = CallData.query(
        ).order(
            -CallData.created_at
        ).fetch(10)
        j = [d.to_json() for d in data]
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(j)

    def post(self):
        j = {}
        for k in self.request.arguments():
            j[k] = self.request.get(k)

        CallData(data=j).put()

        called = self.request.get('To')
        if called is None:
            xml = '''<?xml version="1.0" encoding="UTF-8" ?>
    <Response>
        <Say voice="alice" language="ja-JP">エラーがおきました</Say>
    </Response>
    '''
            self.response.headers['Content-Type'] = 'text/xml'
            self.response.write(xml)
            return

        status = RoombaStatus.get_by_id(called)
        if status is None:
            xml = '''<?xml version="1.0" encoding="UTF-8" ?>
    <Response>
        <Say voice="alice" language="ja-JP">ルンバが接続されていません</Say>
    </Response>
    '''
            self.response.headers['Content-Type'] = 'text/xml'
            self.response.write(xml)
            return

        OrderData(
            called=self.request.get('To'),
            caller=self.request.get('From'),
            data=j,
            talk='',
            command='START',
            time=1,
            oncall=True
        ).put()

        words = [
            u'今日もお仕事お疲れ様、',
            u'今日はゆっくり休んでね',
            u'無理しないでね'
        ]
        xml = u'''<?xml version="1.0" encoding="UTF-8" ?>
<Response>
    <Say voice="alice" language="ja-JP">{word}。{msg}</Say>
    <Record action="http://{appid}.appspot.com/convert" timeout="3" maxlength="5" trim="trim-silence"></Record>
</Response>
'''.format(
        appid=get_application_id(),
        word=words[random.randint(0, len(words)-1)],
        msg=u'ただ今掃除中。とめたい時はピーの後、停止と言ってね' if status.state == 'CLEANING' else u'掃除を始めるよ')

        self.response.headers['Content-Type'] = 'text/xml'
        self.response.write(xml)


stop_words = [u'停', u'止', u'兵士', u'精子', u'トップ', u'困っ', u'待っ']

def get_command(talk):
    if u'歌' in talk:
        return 'SING', None

    if any([w in talk for w in stop_words]):
        return 'STOP', None

    t = None
    if u'時間' in talk:
        i = talk.index(u'時間')
        try:
            s = i - 1
            e = i
            t = int(talk[s:e])
        except Exception as e:
            logging.warning(e)
    return 'START', t


class ConvertPage(webapp2.RequestHandler):
    def get(self):
        data = OrderData.query(
        ).order(
            -OrderData.created_at
        ).fetch(10)
        j = [d.to_json() for d in data]
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(j)

    def post(self):
        j = {}
        for k in self.request.arguments():
            j[k] = self.request.get(k)

        audio_url = self.request.get('RecordingUrl')
        time = None
        script = None
        command = None
        try:
            result = urlfetch.fetch(audio_url, method='GET', validate_certificate=True, deadline=30)
            c = convert(result.content)
            if 'results' in c:
                script = c['results'][0]['alternatives'][0]['transcript']
                command, time = get_command(script)
            else:
                script = ''
                command = 'START'
        except Exception as e:
            logging.warning(e)
            script = None
            command = 'Error'

        OrderData(
            called=self.request.get('To'),
            caller=self.request.get('From'),
            data=j,
            talk=script,
            command=command,
            time=time
        ).put()

        xml = '''<?xml version="1.0" encoding="UTF-8" ?>
<Response>
    <Hangup/>
</Response>
'''
        self.response.headers['Content-Type'] = 'text/xml'
        self.response.write(xml)


class OrderPage(webapp2.RequestHandler):
    def get(self, number):
        data = OrderData.query(
            OrderData.called == number
        ).order(
            -OrderData.created_at
        ).fetch(1)
        j = data[0].to_json() if len(data) > 0 else []
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(j))


class StatePage(webapp2.RequestHandler):
    def get(self, number):
        status = RoombaStatus.get_by_id(number)
        if status is None:
            status = RoombaStatus(id=number)

        state = self.request.get('state')
        status.state = state
        status.put()

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps({'status': 'OK'}))


def convert(audio_file):
    service = build('speech', 'v1beta1', credentials=credentials)
    audio = base64.b64encode(audio_file)
    request = service.speech().syncrecognize(
        body={
            'config': {
                'encoding': 'LINEAR16',
                'sample_rate': 8000,
                'languageCode': 'ja-JP'
            },
            'audio': {
                'content': audio
            }
        })
    response = request.execute()
    logging.debug(json.dumps(response).encode('UTF-8'))
    return response


# Models
class CallData(ndb.Model):
    data = ndb.JsonProperty()
    created_at = ndb.DateTimeProperty(auto_now=True)

    def to_json(self):
        return self.data


class OrderData(ndb.Model):
    called = ndb.StringProperty()
    caller = ndb.StringProperty()
    data = ndb.JsonProperty()
    talk = ndb.StringProperty()
    command = ndb.StringProperty()
    time = ndb.IntegerProperty()
    created_at = ndb.DateTimeProperty(auto_now=True)
    oncall = ndb.BooleanProperty(default=False)

    def to_json(self):
        return {
            'id': self.key.id(),
            'order': self.command,
            'time': self.time,
            'oncall': self.oncall,
            'created_at': self.created_at.strftime('%Y-%m-%dT%H:%M:%SZ')
        }


class RoombaStatus(ndb.Model):
    state = ndb.StringProperty(choices=['CLEANING', 'STOPPING'])


# Main
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/convert', ConvertPage),
    (r'/orders/(.+)', OrderPage),
    (r'/roomba/(.+)', StatePage),
], debug=True)
