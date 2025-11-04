import json
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

codedeploy = boto3.client('codedeploy')
cloudwatch = boto3.client('cloudwatch')


def lambda_handler(event, context):
    """
    Post-traffic hook for CodeDeploy.
    Validates metrics after traffic shift is complete.
    """
    logger.info(f"Post-traffic hook triggered: {json.dumps(event)}")

    deployment_id = event['DeploymentId']
    lifecycle_event_hook_execution_id = event['LifecycleEventHookExecutionId']

    try:
        target_function = os.environ.get('TARGET_FUNCTION')

        logger.info(f"Validating post-deployment metrics for {target_function}")

        # Check CloudWatch metrics for the new version
        # You can add custom metric validation here

        # Example: Check error rate in last 5 minutes
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Errors',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': target_function
                }
            ],
            StartTime=context.invoked_function_arn,  # Last 5 minutes
            EndTime=context.invoked_function_arn,
            Period=300,
            Statistics=['Sum']
        )

        logger.info(f"CloudWatch metrics: {json.dumps(response, default=str)}")

        # Custom validation logic
        # For example: check if error count is below threshold
        # if errors > threshold:
        #     raise Exception("Error rate too high")

        logger.info("Post-traffic validation passed")

        # Report success
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Succeeded'
        )

        return {
            'statusCode': 200,
            'body': json.dumps('Post-traffic validation succeeded')
        }

    except Exception as e:
        logger.error(f"Post-traffic validation failed: {str(e)}", exc_info=True)

        # Report failure - this will trigger rollback
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Failed'
        )

        return {
            'statusCode': 500,
            'body': json.dumps(f'Post-traffic validation failed: {str(e)}')
        }
