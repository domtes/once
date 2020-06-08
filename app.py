#!/usr/bin/env python3

import os
from aws_cdk import (
    core,
    aws_route53 as route53)

from once.once_stack import OnceStack, CustomDomainStack

USE_CUSTOM_DOMAIN = True
DOMAIN_NAME = os.getenv('DOMAIN_NAME')
HOSTED_ZONE_NAME = os.getenv('HOSTED_ZONE_NAME')
HOSTED_ZONE_ID = os.getenv('HOSTED_ZONE_ID')


app = core.App()
once = OnceStack(app, 'once',
    custom_domain=DOMAIN_NAME,
    hosted_zone_id=HOSTED_ZONE_ID,
    hosted_zone_name=HOSTED_ZONE_NAME)

app.synth()
