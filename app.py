#!/usr/bin/env python3

from aws_cdk import core

from once.once_stack import OnceStack


app = core.App()
OnceStack(app, "once")

app.synth()
