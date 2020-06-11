#!/usr/bin/env python3

import os
import base64
import configparser
from typing import Optional

from aws_cdk import core
from once.once_stack import OnceStack, CustomDomainStack


ONCE_CONFIG_FILE = os.getenv('ONCE_CONFIG_FILE', os.path.expanduser('~/.once'))

SECRET_KEY = os.getenv('SECRET_KEY')
CUSTOM_DOMAIN = os.getenv('CUSTOM_DOMAIN')
HOSTED_ZONE_NAME = os.getenv('HOSTED_ZONE_NAME')
HOSTED_ZONE_ID = os.getenv('HOSTED_ZONE_ID')


def generate_random_key() -> str:
    return base64.b64encode(os.urandom(128)).decode('utf-8')


def generate_config(secret_key: Optional[str] = None,
    custom_domain: str = None,
    hosted_zone_name: str = None,
    hosted_zone_id: str = None) -> configparser.ConfigParser:
    config = configparser.ConfigParser()

    config['once'] = {
        'secret_key': secret_key or generate_random_key(),
    }

    config['deployment'] = {}
    if all([custom_domain, hosted_zone_name, hosted_zone_id]):
        config['once']['base_url'] = f'https://{custom_domain}'
        config['deployment'] = {
            'custom_domain': custom_domain,
            'hosted_zone_name': hosted_zone_name,
            'hosted_zone_id': hosted_zone_id
        }
    return config


def get_config(config_gile: str = ONCE_CONFIG_FILE) -> configparser.ConfigParser:
    if not os.path.exists(ONCE_CONFIG_FILE):
        print(f'Generating configuration file at {ONCE_CONFIG_FILE}')
        with open(ONCE_CONFIG_FILE, 'w') as config_file:
            config = generate_config(
                secret_key=SECRET_KEY,
                custom_domain=CUSTOM_DOMAIN,
                hosted_zone_name=HOSTED_ZONE_NAME,
                hosted_zone_id=HOSTED_ZONE_ID)
            config.write(config_file)
    else:
        config = configparser.ConfigParser()
        config.read(ONCE_CONFIG_FILE)
    return config


def main():
    config = get_config()

    kwargs = {'secret_key': config['once']['secret_key']}
    if config.has_section('deployment'):
        kwargs.update(config['deployment'])

    app = core.App()
    once = OnceStack(app, 'once', **kwargs)
    app.synth()


if __name__ == '__main__':
    main()
