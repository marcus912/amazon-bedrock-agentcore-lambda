import json
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

codedeploy = boto3.client('codedeploy')
lambda_client = boto3.client('lambda')


def lambda_handler(event, context):
    """
    Pre-traffic hook for CodeDeploy.
    Runs validation tests before shifting traffic to new version.
    """
    logger.info(f"Pre-traffic hook triggered: {json.dumps(event)}")

    deployment_id = event['DeploymentId']
    lifecycle_event_hook_execution_id = event['LifecycleEventHookExecutionId']

    try:
        # Get the new version of the function
        target_function = os.environ.get('TARGET_FUNCTION')

        # Run smoke tests on new version
        logger.info(f"Running smoke tests on {target_function}")

        # Test 1: Invoke with health check
        test_event = {
            'test': True,
            'sessionId': 'pre-deployment-test',
            'inputText': 'Health check'
        }

        response = lambda_client.invoke(
            FunctionName=target_function,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_event)
        )

        response_payload = json.loads(response['Payload'].read())
        logger.info(f"Test response: {json.dumps(response_payload)}")

        # Validate response
        if response.get('FunctionError'):
            raise Exception(f"Function returned error: {response_payload}")

        if response.get('StatusCode') != 200:
            raise Exception(f"Unexpected status code: {response.get('StatusCode')}")

        # Additional validation checks
        body = json.loads(response_payload.get('body', '{}'))
        if response_payload.get('statusCode') not in [200, 400]:  # 400 is ok if agent ID not configured
            raise Exception(f"Invalid response status: {response_payload.get('statusCode')}")

        logger.info("Pre-traffic validation passed")

        # Report success
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Succeeded'
        )

        return {
            'statusCode': 200,
            'body': json.dumps('Pre-traffic validation succeeded')
        }

    except Exception as e:
        logger.error(f"Pre-traffic validation failed: {str(e)}", exc_info=True)

        # Report failure - this will prevent deployment
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status='Failed'
        )

        return {
            'statusCode': 500,
            'body': json.dumps(f'Pre-traffic validation failed: {str(e)}')
        }
