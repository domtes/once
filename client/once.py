'''
Simple command to share one-time files
'''

import os
import base64
import configparser
import hashlib
import hmac
import json
import time
from datetime import datetime
from urllib.parse import quote_plus, urljoin

import click
import requests
from pygments import highlight, lexers, formatters


ONCE_CONFIG_FILE = os.getenv('ONCE_CONFIG_FILE', os.path.expanduser('~/.once'))
ONCE_SIGNATURE_HEADER = 'x-once-signature'
ONCE_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S%f'


def highlight_json(obj):
    formatted_json = json.dumps(obj, sort_keys=True, indent=4)
    return highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())


def echo_obj(obj):
    click.echo(highlight_json(obj))


def get_config(config_file: str = ONCE_CONFIG_FILE) -> configparser.ConfigParser:
    if not os.path.exists(config_file):
        raise ValueError(f'Config file not found at {config_file}')
    config = configparser.ConfigParser()
    config.read(ONCE_CONFIG_FILE)
    return config


def api_req(method: str, url: str, verbose: bool = False, **kwargs):
    config = get_config()
    if not config.has_option('once', 'base_url'):
        raise ValueError(f'Configuration file at {ONCE_CONFIG_FILE} misses `base_url` option')

    base_url = os.getenv('ONCE_API_URL', config['once']['base_url'])
    secret_key = base64.b64decode(os.getenv('ONCE_SECRET_KEY', config['once']['secret_key']))

    method = method.lower()
    if method not in ['get', 'post']:
        raise ValueError(f'Unsupported HTTP method "{method}"')

    actual_url = urljoin(base_url, url)

    if verbose:
        print(f'{method.upper()} {actual_url}')

    req = requests.Request(method=method, url=actual_url, **kwargs).prepare()
    plain_text = req.path_url.encode('utf-8')
    hmac_obj = hmac.new(secret_key, msg=plain_text, digestmod=hashlib.sha256)
    req.headers[ONCE_SIGNATURE_HEADER] = base64.b64encode(hmac_obj.digest())

    response = requests.Session().send(req)

    if verbose:
        print(f'Server response status: {response.status_code}')
        echo_obj(response.json())

    return response


@click.command('share')
@click.argument('file', type=click.File(mode='rb'), required=True)
@click.option('--verbose', '-v', is_flag=True, default=False, help='Enables verbose output.')
def share(file: click.File, verbose: bool):
    entry = api_req('GET', '/',
        params={
            'f': quote_plus(os.path.basename(file.name)),
            't': datetime.utcnow().strftime(ONCE_TIMESTAMP_FORMAT)
        },
        verbose=verbose).json()

    once_url = entry['once_url']
    upload_data = entry['presigned_post']
    files = {'file': file}

    upload_started = time.time()
    response = requests.post(upload_data['url'],
        data=upload_data['fields'],
        files=files)

    upload_time = time.time() - upload_started
    print(f"File uploaded in {upload_time}s")    
    print(f"File can be downloaded once at: {once_url}")


if __name__ == '__main__':
    share()
