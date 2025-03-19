from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_sqs as sqs,
    aws_ecs as ecs,
    aws_ecr as ecr,
    Duration
)
from constructs import Construct
import os

class ContainerLifecycleStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create ECS Cluster
        cluster = ecs.Cluster(self, "ContainerLifecycleCluster",
            cluster_name="container-lifecycle-cluster",
            container_insights=True
        )

        # Create Lambda function
        lambda_function = _lambda.Function(self, "ContainerLifecycleFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="container_manager.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            environment={
                "ECS_CLUSTER_NAME": cluster.cluster_name
            },
            timeout=Duration.minutes(5)
        )

        # Grant necessary permissions to Lambda
        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:ListServices",
                    "ecs:DescribeServices",
                    "ecs:UpdateService",
                    "ecs:ListTasks",
                    "ecs:DescribeTasks",
                    "ecr:ListImages",
                    "ecr:DeleteImage",
                    "cloudwatch:GetMetricData",
                    "ssm:GetParameter"
                ],
                resources=["*"]
            )
        )

        # Create CloudWatch Event Rule
        rule = events.Rule(self, "ContainerLifecycleRule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            targets=[targets.LambdaFunction(lambda_function)]
        )

        # Create SNS Topic for notifications
        topic = sns.Topic(self, "ContainerLifecycleTopic",
            display_name="Container Lifecycle Notifications",
            topic_name="container-lifecycle-notifications"
        )

        # Create SQS Queue for failed operations
        dead_letter_queue = sqs.Queue(self, "ContainerLifecycleDLQ",
            queue_name="container-lifecycle-dlq",
            retention_period=Duration.days(14),
            visibility_timeout=Duration.seconds(30)
        )

        # Add SQS subscription to SNS topic
        topic.add_subscription(
            subscriptions.SqsSubscription(dead_letter_queue)
        )

        # Output important information
        self.cluster_name = cluster.cluster_name
        self.lambda_function_name = lambda_function.function_name
        self.sns_topic_arn = topic.topic_arn
        self.sqs_queue_url = dead_letter_queue.queue_url

        # Export values
        self.export_value("ClusterName", cluster.cluster_name)
        self.export_value("LambdaFunctionName", lambda_function.function_name)
        self.export_value("SNSTopicArn", topic.topic_arn)
        self.export_value("SQSQueueUrl", dead_letter_queue.queue_url) 