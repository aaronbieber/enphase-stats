"""Retrieve and marshal energy data from Enphase Englighten API."""
import sys
import time
from datetime import datetime
from pprint import pprint
import base64
import shelve
import requests
import pytz
import whisper
import config
from carbon_client import CarbonClient


class EnphaseClient():
    '''
    Send requests to the Enphase Enlighten API.
    '''
    base_url = 'https://api.enphaseenergy.com'
    token_url = f'{base_url}/oauth/token'
    redirect_uri = f'{base_url}/oauth/redirect_uri'

    def __init__(self, token_manager):
        self.token_manager = token_manager
        self.get_auth_code()

    def client_code(self):
        '''
        Return the "code" used in token requests.
        '''
        return base64.b64encode(
            (whisper.CLIENT_ID + ':' + whisper.CLIENT_SECRET).encode()).decode()

    def get_system_id(self):
        '''
        Retrieve the system ID from the API.
        '''
        if len(whisper.SYSTEM_ID) > 0:
            return

        try:
            res = requests.get(f'{self.base_url}/api/v4/systems',
                               params={'key': whisper.API_KEY},
                               headers={
                                   'Authorization': f'Bearer {self.token_manager.access()}'},
                               timeout=0.5)
        except TimeoutError as ex:
            print('Timed out while requesting system data:', ex)
            sys.exit(1)

        if not 'systems' in res.json():
            print('Systems data request succeeded, but system data not found.')
            print('Full response data follows:')
            pprint(res.json())
            sys.exit(1)

        print('')
        print('✅ System ID(s) retrieved!')
        print('')
        for system in res.json()['systems']:
            print(f" 🔸 {system['name']}: {system['system_id']}")

        print('')
        print('Copy the system ID you are monitoring into your whisper.py.')
        sys.exit(0)

    def get_auth_code(self):
        '''
        Walk the user through authorizing the app and getting an auth code.
        '''
        if len(whisper.AUTH_CODE) > 0:
            return

        print('')
        print('✨✨ Welcome! ✨✨')
        print('')
        print("It looks like you haven't run this script before. You'll need to authorize the")
        print('app to retrieve data for your system by completing an OAuth handshake on the')
        print('web and recording the resulting client code.')

        if len(whisper.CLIENT_ID) == 0:
            print('')
            print('Before we can continue, you must create a new application in the developer')
            print('portal at https://developer-v4.enphase.com/ and copy your client ID and')
            print("client secret into the whisper.py file. After you've done that, run this")
            print('script again.')
            sys.exit(0)

        print('')
        print('Visit the following URL:')
        print(f'{self.base_url}/oauth/authorize?response_type=code' +
              f'&client_id={whisper.CLIENT_ID}&redirect_uri={self.redirect_uri}')
        print('')
        print('❗IMPORTANT❗')
        print('After logging in and authorizing the app to connect to your system, you should')
        print('be redirected to a simple page displaying the six-character auth code. DO NOT')
        print('LOSE THAT CODE. Add it to your whisper.py file.')
        sys.exit(0)

    def get_tokens(self):
        '''
        Retrieve tokens.
        '''
        res = requests.post(self.token_url,
                            params={'grant_type': 'authorization_code',
                                    'redirect_uri': self.redirect_uri,
                                    'code': whisper.AUTH_CODE},
                            headers={
                                'Authorization': f'Basic {self.client_code()}'},
                            timeout=0.5)

        data = res.json()

        if 'error_description' in data:
            print('Request returned error:', data['error_description'])
            return False

        return {'access': data['access_token'],
                'refresh': data['refresh_token'],
                'expire': int(time.time()) + data['expires_in']}

    def refresh_tokens(self, refresh_token):
        '''
        Refresh the access tokens.
        '''
        res = requests.post(f'{self.base_url}/oauth/token',
                            params={'grant_type': 'refresh_token',
                                    'refresh_token': refresh_token},
                            headers={
                                'Authorization': f'Basic {self.client_code()}'},
                            timeout=0.5)

        data = res.json()

        if 'error_description' in data:
            print('Request returned error:', data['error_description'])
            return False

        return {'access': data['access_token'],
                'refresh': data['refresh_token'],
                'expire': int(time.time()) + data['expires_in']}

    def get_consumption(self, access_token, since=None):
        '''
        Get consumption meter data.
        '''
        self.get_system_id()

        if since is None:
            since = int(datetime.now(pytz.utc).replace(hour=0,
                                                       minute=0,
                                                       second=0,
                                                       microsecond=0).timestamp())

        try:
            res = requests.get(f'{self.base_url}/api/v4/systems/{whisper.SYSTEM_ID}' +
                               '/telemetry/consumption_meter',
                               params={'key': whisper.API_KEY,
                                       'granularity': 'day'},
                               headers={
                                   'Authorization': f'Bearer {access_token}'},
                               timeout=0.5)
        except TimeoutError as ex:
            print('Timed out while requesting consumption meter data:', ex)
            return []

        if not 'intervals' in res.json():
            print('Unexpected response format:', res.json())
            return []

        intervals = []
        for interval in res.json()['intervals']:
            if interval['end_at'] > since:
                intervals.append({
                    'end_at': interval['end_at'],
                    'wh': interval['enwh']
                })

        return intervals

    def get_production(self, access_token, since=None):
        '''
        Get production meter data.
        '''
        self.get_system_id()

        if since is None:
            since = int(datetime.now(pytz.utc).replace(hour=0,
                                                       minute=0,
                                                       second=0,
                                                       microsecond=0).timestamp())

        try:
            res = requests.get(f'{self.base_url}/api/v4/systems/{whisper.SYSTEM_ID}' +
                               '/telemetry/production_meter',
                               params={'key': whisper.API_KEY,
                                       'granularity': 'day'},
                               headers={
                                   'Authorization': f'Bearer {access_token}'},
                               timeout=0.5)
        except TimeoutError as ex:
            print('Timed out while requesting production meter data:', ex)
            return []

        if not 'intervals' in res.json():
            print('Unexpected response format:', res.json())
            return []

        intervals = []
        for interval in res.json()['intervals']:
            if interval['end_at'] > since:
                intervals.append({
                    'end_at': interval['end_at'],
                    'wh': interval['wh_del']
                })

        return intervals


class TokenManager():
    '''
    Manage access tokens.
    '''
    shelf = shelve.open('tokens')

    def __init__(self):
        result = self.load()

        if result:
            print('Recalled tokens from file')
        else:
            self.request_tokens()

    def load(self):
        '''
        Verify existence of required values.
        '''
        if ('access' in self.shelf and
            'refresh' in self.shelf and
                'expire' in self.shelf):

            if self.shelf['expire'] <= int(time.time()):
                self.refresh_tokens()

            return True

        return False

    def save(self, token_data):
        '''
        Update tokens and flush to disk.
        '''
        self.shelf['access'] = token_data['access']
        self.shelf['refresh'] = token_data['refresh']
        self.shelf['expire'] = token_data['expire']

    def request_tokens(self):
        '''
        Request new tokens from the API.
        '''
        print('Requesting a new set of tokens...')
        enphase = EnphaseClient(self)
        token_data = enphase.get_tokens()

        if token_data is not False:
            self.save(token_data)

    def refresh_tokens(self):
        '''
        Refresh tokens using our refresh token.
        '''
        enphase = EnphaseClient(self)
        token_data = enphase.refresh_tokens(self.refresh())

        if token_data is not False:
            self.save(token_data)

    def access(self):
        '''
        Return the current access token.
        '''
        if len(self.shelf['access']):
            return self.shelf['access']

        return ''

    def refresh(self):
        '''
        Return the current refresh token.
        '''
        if len(self.shelf['refresh']):
            return self.shelf['refresh']

        return ''


def main():
    '''
    The entry point for the program.
    '''
    print("Starting up...")

    cache = shelve.open('request_cache')
    token_manager = TokenManager()

    print('Tokens expire on',
          time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(token_manager.shelf['expire'])))

    print('Last interval ended at',
          time.strftime('%Y-%m-%d at %H:%M:%S',
                        time.localtime(cache['last_interval'])),
          '-', int(time.time()) - cache['last_interval'], '△ second(s).')
    if ('last_interval' in cache and int(time.time()) - cache['last_interval'] < 900):
        print('Not ready to request next interval.')
        sys.exit(0)

    enphase = EnphaseClient(token_manager)
    consumption_res = enphase.get_consumption(
        token_manager.access(), cache['last_interval'])
    production_res = enphase.get_production(
        token_manager.access(), cache['last_interval'])

    if len(consumption_res) == 0 or len(production_res) == 0:
        print("Couldn't retrieve (or didn't receive) meter data; aborting.")
        sys.exit(1)

    cache['last_interval'] = consumption_res[-1]['end_at']

    carbon = CarbonClient(config.CARBON_HOST, config.CARBON_PICKLE_PORT)

    cons_stats = map(
        lambda s: ('solar.consumption', (s['end_at'], s['wh'])),
        consumption_res
    )
    prod_stats = map(
        lambda s: ('solar.production', (s['end_at'], s['wh'])),
        production_res
    )
    stats = list(cons_stats) + list(prod_stats)

    pprint(stats)

    carbon.send_pickle(stats)
    cache.close()


if __name__ == '__main__':
    main()
