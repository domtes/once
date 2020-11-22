import os
import io
import json
import logging
from typing import Dict

import boto3
from boto3.dynamodb.conditions import Key


def is_debug_enabled() -> bool:
    value = os.getenv("DEBUG", "false").lower()
    if value in ["false", "0"]:
        return False
    else:
        return bool(value)


DEBUG = is_debug_enabled()
FILES_BUCKET = os.getenv("FILES_BUCKET")
FILES_TABLE_NAME = os.getenv("FILES_TABLE_NAME")


log = logging.getLogger()
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)


def on_event(event, context):
    log.debug(f"Event received: {event}")
    log.debug(f"Context is: {context}")
    log.debug(f"Debug mode is {DEBUG}")
    log.debug(f'Files bucket is "{FILES_BUCKET}"')

    dynamodb = boto3.client("dynamodb")
    response = dynamodb.scan(
        TableName=FILES_TABLE_NAME,
        Select="ALL_ATTRIBUTES",
        FilterExpression="deleted = :deleted",
        ExpressionAttributeValues={":deleted": {"BOOL": True}},
    )

    s3 = boto3.client("s3")
    for item in response["Items"]:
        object_name = item["object_name"]["S"]
        log.info(f"Deleting file {object_name}")
        try:
            s3.delete_object(Bucket=FILES_BUCKET, Key=object_name)
        except:
            log.exception("Could not delete file {object_name}")

        response = dynamodb.delete_item(TableName=FILES_TABLE_NAME, Key={"id": item["id"]})
        log.debug(f"dynamodb delete item: {response}")
