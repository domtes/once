import base64
import hashlib
import hmac
import json
import logging
import os
import random
import string
from typing import Dict
from urllib.parse import quote_plus, urlencode

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


log = logging.getLogger()
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)


class BadRequestError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


def on_event(event, context):
    log.info(f'Event received: {event}')
    log.info(f'Context is: {context}')
    log.info(f'Requests library version: {requests.__version__}')

    log.debug(f'Debug mode is {DEBUG}')
    log.debug(f'App URL is "{APP_URL}"')
    log.debug(f'Files bucket is "{FILES_BUCKET}"')
    log.debug(f'Files Dynamodb table name is "{FILES_TABLE_NAME}"')
    log.debug(f'S3 region name is: "{S3_REGION_NAME}"')
    log.debug(f'S3 signature algorithm version is "{S3_SIGNATURE_VERSION}"')
    log.debug(f'Pre-signed urls will expire after {EXPIRATION_TIMEOUT} seconds')

    q = event.get('queryStringParameters', {})
    filename = q.get('f')
    response_code = 200
    response = {}
    try:
        if filename is None:
            raise BadRequestError('Provide a valid value for the `f` query parameter')

        domain = string.ascii_uppercase + string.ascii_lowercase + string.digits
        entry_id = ''.join(random.choice(domain) for _ in range(6))
        object_name = f'{entry_id}/{filename}'
        response['once_url'] = f'{APP_URL}{entry_id}/{filename}'

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

        log.debug(f'Presigned-Post response: {presigned_post}')

        # Long life and prosperity!
        log.info(f'Authorized upload request for {object_name}')
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



# def validate_request(event: Dict, secret_key: str) -> bool:
#     '''
#     Validates the HMAC(SHA256) signature against the given `request`.
#     '''

#     # discard any url prefix before '/v1/'
#     path = event['rawPath']
#     canonicalized_url = path[path.find('/v1/'):]

#     if 'queryStringParameters' in event:
#         qs = urlencode(event['queryStringParameters'], quote_via=quote_plus)
#         canonicalized_url = f'{canonicalized_url}?{qs}'

#     plain_text = canonicalized_url.encode('utf-8')
#     log.debug(f'Plain text: {plain_text}')

#     encoded_signature = event['headers'][HMAC_SIGNATURE_HEADER]
#     log.debug(f'Received signature: {encoded_signature}')

#     signature_value = base64.b64decode(encoded_signature)

#     hmac_obj = hmac.new(base64.b64decode(secret_key),
#                         msg=plain_text,
#                         digestmod=hashlib.sha256)

#     calculated_signature = hmac_obj.digest()
#     return calculated_signature == signature_value


def create_presigned_post(bucket_name: str, object_name: str,
                          fields=None, conditions=None, expiration=3600):
    """Generate a presigned URL S3 POST request to upload a file

    :param bucket_name: string
    :param object_name: string
    :param fields: Dictionary of prefilled form fields
    :param conditions: List of conditions to include in the policy
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Dictionary with the following keys:
        url: URL to post to
        fields: Dictionary of form fields and values to submit with the POST
    :return: None if error.
    """
    s3_client = boto3.client('s3',
        region_name=S3_REGION_NAME,
        config=Config(signature_version=S3_SIGNATURE_VERSION))

    return s3_client.generate_presigned_post(
        bucket_name, object_name,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expiration)
