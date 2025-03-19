import boto3
import json
import logging
import os
import time
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
ecs = boto3.client('ecs')
ecr = boto3.client('ecr')
cloudwatch = boto3.client('cloudwatch')
ssm = boto3.client('ssm')

def get_slack_webhook():
    """Retrieve Slack webhook URL from SSM Parameter Store."""
    try:
        response = ssm.get_parameter(
            Name="/container-lifecycle/slack-webhook",
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Failed to get Slack webhook: {str(e)}")
        return None

def send_slack_notification(message):
    """Send notification to Slack channel."""
    webhook_url = get_slack_webhook()
    if not webhook_url:
        logger.error("Slack webhook URL not configured")
        return

    try:
        payload = {
            "text": message,
            "username": "Container Lifecycle Manager",
            "icon_emoji": ":docker:",
            "channel": "#container-alerts"
        }
        requests.post(webhook_url, json=payload)
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {str(e)}")

def get_container_metrics(cluster_name, service_name):
    """Get container metrics from CloudWatch."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        response = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    'Id': 'm1',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'ECS/ContainerInsights',
                            'MetricName': 'CPUUtilization',
                            'Dimensions': [
                                {'Name': 'ClusterName', 'Value': cluster_name},
                                {'Name': 'ServiceName', 'Value': service_name}
                            ]
                        },
                        'Period': 300,
                        'Stat': 'Average'
                    },
                    'StartTime': start_time,
                    'EndTime': end_time
                }
            ]
        )
        return response['MetricDataResults'][0]['Values']
    except Exception as e:
        logger.error(f"Failed to get container metrics: {str(e)}")
        return []

def check_container_health(cluster_name, service_name):
    """Check container health and send alerts if needed."""
    try:
        # Get service details
        response = ecs.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )
        
        service = response['services'][0]
        
        # Check for failed deployments
        if service['runningCount'] < service['desiredCount']:
            message = f"⚠️ Service {service_name} has failed deployments. Running: {service['runningCount']}, Desired: {service['desiredCount']}"
            send_slack_notification(message)
        
        # Check CPU utilization
        metrics = get_container_metrics(cluster_name, service_name)
        if metrics and metrics[-1]['Value'] > 80:
            message = f"⚠️ High CPU utilization detected for service {service_name}: {metrics[-1]['Value']}%"
            send_slack_notification(message)
            
    except Exception as e:
        logger.error(f"Failed to check container health: {str(e)}")

def cleanup_unused_containers(cluster_name):
    """Clean up unused containers and images."""
    try:
        # List all services in the cluster
        response = ecs.list_services(cluster=cluster_name)
        
        for service_arn in response['serviceArns']:
            service_name = service_arn.split('/')[-1]
            
            # Get service details
            service_response = ecs.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            service = service_response['services'][0]
            
            # Check if service is inactive (no running tasks for 24 hours)
            if service['runningCount'] == 0:
                # Get last activity timestamp
                last_activity = service.get('lastEvent', {}).get('createdAt', None)
                if last_activity and (datetime.now() - last_activity).days >= 1:
                    message = f"🧹 Cleaning up inactive service: {service_name}"
                    logger.info(message)
                    send_slack_notification(message)
                    
                    # Update service to 0 desired count
                    ecs.update_service(
                        cluster=cluster_name,
                        service=service_name,
                        desiredCount=0
                    )
                    
    except Exception as e:
        logger.error(f"Failed to cleanup unused containers: {str(e)}")

def lambda_handler(event, context):
    """Main Lambda handler function."""
    try:
        # Get cluster name from environment variable
        cluster_name = os.environ['ECS_CLUSTER_NAME']
        
        # Check container health
        response = ecs.list_services(cluster=cluster_name)
        for service_arn in response['serviceArns']:
            service_name = service_arn.split('/')[-1]
            check_container_health(cluster_name, service_name)
        
        # Cleanup unused containers
        cleanup_unused_containers(cluster_name)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Container lifecycle management completed successfully')
        }
        
    except Exception as e:
        error_message = f"Error in container lifecycle management: {str(e)}"
        logger.error(error_message)
        send_slack_notification(f"❌ {error_message}")
        return {
            'statusCode': 500,
            'body': json.dumps(error_message)
        } 