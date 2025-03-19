#!/usr/bin/env python3
import aws_cdk as cdk
from container_lifecycle_stack import ContainerLifecycleStack
import os

app = cdk.App()
ContainerLifecycleStack(app, "ContainerLifecycleStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

app.synth() 