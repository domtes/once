'''
Simple command to share one-time files
'''

import os
import json
import time
import urllib

import click
import requests
from pygments import highlight, lexers, formatters


ONCE_API_URL = os.getenv('ONCE_API_URL')


def highlight_json(obj):
    formatted_json = json.dumps(obj, sort_keys=True, indent=4)
    return highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())


def echo_obj(obj):
    click.echo(highlight_json(obj))


def api_req(method: str, url: str, verbose: bool = False, **kwargs):
    method = method.lower()
    if method not in ['get', 'post']:
        raise ValueError(f'Unsupported HTTP method "{method}"')

    actual_url = f'{ONCE_API_URL}{url}'

    if verbose:
        print(f'{method.upper()} {actual_url}')

    response = getattr(requests, method)(actual_url, **kwargs)

    if verbose:
        print(f'Server response status: {response.status_code}')
        echo_obj(response.json())

    return response


@click.command('share')
@click.argument('file', type=click.File(mode='rb'), required=True)
@click.option('--verbose', '-v', is_flag=True, default=False, help='Enables verbose output.')
def share(file: click.File, verbose: bool):
    entry = api_req('GET', '/',
        params={'f': urllib.parse.quote_plus(os.path.basename(file.name))},
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
