# coding: UTF-8
import base64
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from googleapiclient.discovery import build
import json
import logging
from oauth2client.client import GoogleCredentials
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

        xml = '''<?xml version="1.0" encoding="UTF-8" ?>
<Response>
    <Say>Hello this is Roomba</Say>
    <Record action="http://tottorise.appspot.com/convert" timeout="3" maxlength="4" trim="trim-silence"></Record>
</Response>
'''
        self.response.headers['Content-Type'] = 'text/xml'
        self.response.write(xml)


def get_command(talk):
    if u'停止' in talk:
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
                command = 'Error'
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


class ConvertTest(webapp2.RequestHandler):
    def get(self):
        convert()


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

    def to_json(self):
        return self.data


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/convert', ConvertPage),
    ('/convert-test', ConvertTest),
], debug=True)
