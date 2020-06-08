import base64
import hashlib
import hmac
import json
import logging
import os
import random
import string
from datetime import datetime, timedelta
from typing import Dict
from urllib.parse import quote, quote_plus, unquote_plus, urlencode

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError


def is_debug_enabled() -> bool:
    value = os.getenv('DEBUG', 'false').lower()
    if value in ['false', '0']:
        return False
    else:
        return bool(value)


DEBUG = is_debug_enabled()
APP_URL = os.getenv('APP_URL')
EXPIRATION_TIMEOUT = int(os.getenv('EXPIRATION_TIMEOUT', 60*5))
FILES_BUCKET = os.getenv('FILES_BUCKET')
FILES_TABLE_NAME = os.getenv('FILES_TABLE_NAME')
S3_REGION_NAME = os.getenv('S3_REGION_NAME', 'eu-west-1')
S3_SIGNATURE_VERSION = os.getenv('S3_SIGNATURE_VERSION', 's3v4')
SECRET_KEY = base64.b64decode(os.getenv('SECRET_KEY'))
SIGNATURE_HEADER = os.getenv('SIGNATURE_HEADER', 'x-once-signature')
SIGNATURE_TIME_TOLERANCE = int(os.getenv('SIGNATURE_TIME_TOLERANCE', 5))
TIMESTAMP_FORMAT_STRING = os.getenv('TIMESTAMP_FORMAT_STRING', '%d%m%Y%H%M%S')
TIMESTAMP_PARAMETER_FORMAT = '%Y%m%d%H%M%S%f'


log = logging.getLogger()
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)


class BadRequestError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


def create_presigned_post(bucket_name: str, object_name: str,
                          fields=None, conditions=None, expiration=3600) -> Dict:
    '''
    Generate a presigned URL S3 POST request to upload a file
    '''
    s3_client = boto3.client('s3',
        region_name=S3_REGION_NAME,
        config=Config(signature_version=S3_SIGNATURE_VERSION))

    return s3_client.generate_presigned_post(
        bucket_name, object_name,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expiration)


def validate_signature(event: Dict, secret_key: bytes) -> bool:
    canonicalized_url = event['rawPath']
    if 'queryStringParameters' in event:
        qs = urlencode(event['queryStringParameters'], quote_via=quote_plus)
        canonicalized_url = f'{canonicalized_url}?{qs}'

    plain_text = canonicalized_url.encode('utf-8')
    log.debug(f'Plain text: {plain_text}')

    encoded_signature = event['headers'][SIGNATURE_HEADER]
    log.debug(f'Received signature: {encoded_signature}')

    signature_value = base64.b64decode(encoded_signature)

    hmac_obj = hmac.new(secret_key,
                        msg=plain_text,
                        digestmod=hashlib.sha256)

    calculated_signature = hmac_obj.digest()
    return calculated_signature == signature_value


def validate_timestamp(timestamp: str, current_time: datetime=None) -> bool:
    if current_time is None:
        current_time = datetime.utcnow()

    try:
        file_loading_time = datetime.strptime(timestamp, TIMESTAMP_PARAMETER_FORMAT)
        return current_time - file_loading_time <= timedelta(seconds=SIGNATURE_TIME_TOLERANCE)
    except:
        log.error(f'Could not validate timestamp {timestamp} according to the format: {TIMESTAMP_PARAMETER_FORMAT}')
        return False


def on_event(event, context):
    log.debug(f'Event received: {event}')
    log.debug(f'Context is: {context}')
    log.debug(f'Requests library version: {requests.__version__}')

    log.debug(f'Debug mode is {DEBUG}')
    log.debug(f'App URL is "{APP_URL}"')
    log.debug(f'Files bucket is "{FILES_BUCKET}"')
    log.debug(f'Files Dynamodb table name is "{FILES_TABLE_NAME}"')
    log.debug(f'S3 region name is: "{S3_REGION_NAME}"')
    log.debug(f'S3 signature algorithm version is "{S3_SIGNATURE_VERSION}"')
    log.debug(f'Pre-signed urls will expire after {EXPIRATION_TIMEOUT} seconds')

    q = event.get('queryStringParameters', {})
    filename = unquote_plus(q.get('f'))
    timestamp = unquote_plus(q.get('t'))

    response_code = 200
    response = {}
    try:
        if filename is None:
            raise BadRequestError('Provide a valid value for the `f` query parameter')

        if timestamp is None:
            raise BadRequestError('Please provide a valid value for the `t` query parameter')

        if not validate_timestamp(timestamp):
            log.error('Request timestamp is not valid')
            raise UnauthorizedError('Your request cannot be authorized')

        if not validate_signature(event, SECRET_KEY):
            log.error('Request signature is not valid')
            raise UnauthorizedError('Your request cannot be authorized')

        domain = string.ascii_uppercase + string.ascii_lowercase + string.digits
        entry_id = ''.join(random.choice(domain) for _ in range(6))
        object_name = f'{entry_id}/{filename}'
        response['once_url'] = f'{APP_URL}{entry_id}/{quote(filename)}'

        dynamodb = boto3.client('dynamodb')
        dynamodb.put_item(
            TableName=FILES_TABLE_NAME,
            Item={
                'id': {'S': entry_id},
                'object_name': {'S': object_name}
            })

        log.debug(f'Creating pre-signed post for {object_name} on '
                  f'{FILES_BUCKET} (expiration={EXPIRATION_TIMEOUT})')

        presigned_post = create_presigned_post(
            bucket_name=FILES_BUCKET,
            object_name=object_name,
            expiration=EXPIRATION_TIMEOUT)

        log.info(f'Authorized upload request for {object_name}')
        log.debug(f'Presigned-Post response: {presigned_post}')
        response['presigned_post'] = presigned_post
    except BadRequestError as e:
        response_code = 400
        response = dict(message=str(e))
    except UnauthorizedError:
        response_code = 401
        response = dict(message=str(e))
    except Exception as e:
        response_code = 500
        response = dict(message=str(e))
    finally:
        return {
            'statusCode': response_code,
            'body': json.dumps(response)
        }
