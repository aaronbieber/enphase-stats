"""Retrieve and marshal energy data from Enphase Englighten API."""
import sys
import time
from datetime import datetime
import base64
import shelve
import requests
import pytz
import whisper
import config
from carbon_client import CarbonClient

from pprint import pprint


class EnphaseClient():
    '''
    Send requests to the Enphase Enlighten API.
    '''
    base_url = 'https://api.enphaseenergy.com'
    token_url = f'{base_url}/oauth/token'
    redirect_uri = f'{base_url}/oauth/redirect_uri'

    def client_code(self):
        '''
        Return the "code" used in token requests.
        '''
        return base64.b64encode(
            (whisper.CLIENT_ID + ':' + whisper.CLIENT_SECRET).encode()).decode()

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
        if since == None:
            since = int(datetime.now(pytz.utc).replace(hour=0,
                                                       minute=0,
                                                       second=0,
                                                       microsecond=0).timestamp())

        try:
            res = requests.get(f'{self.base_url}/api/v4/systems/{whisper.SYSTEM_ID}/telemetry/consumption_meter',
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
        if since == None:
            since = int(datetime.now(pytz.utc).replace(hour=0,
                                                       minute=0,
                                                       second=0,
                                                       microsecond=0).timestamp())

        try:
            res = requests.get(f'{self.base_url}/api/v4/systems/{whisper.SYSTEM_ID}/telemetry/production_meter',
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

    def __init__(self) -> None:
        result = self.load()

        if result:
            print('Recalled tokens from file')
        else:
            self.request_tokens()

    def load(self) -> bool:
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

    def save(self, token_data) -> bool:
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
        enphase = EnphaseClient()
        token_data = enphase.get_tokens()

        if token_data is not False:
            self.save(token_data)

    def refresh_tokens(self):
        '''
        Refresh tokens using our refresh token.
        '''
        enphase = EnphaseClient()
        token_data = enphase.refresh_tokens(self.refresh())

        if token_data is not False:
            self.save(token_data)

    def access(self) -> str:
        '''
        Return the current access token.
        '''
        if len(self.shelf['access']):
            return self.shelf['access']

        return ''

    def refresh(self) -> str:
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

    enphase = EnphaseClient()
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
