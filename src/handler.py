import json
import os
import boto3
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock client
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# Environment variables
BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler to invoke Bedrock AgentCore agent.

    Expected event format:
    {
        "sessionId": "unique-session-id",
        "inputText": "User's question or prompt",
        "enableTrace": false
    }
    """
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Validate required parameters
        if not BEDROCK_AGENT_ID:
            raise ValueError("BEDROCK_AGENT_ID environment variable is not set")

        # Extract parameters from event
        session_id = event.get('sessionId', context.request_id)
        input_text = event.get('inputText', '')
        enable_trace = event.get('enableTrace', False)

        if not input_text:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'inputText is required'
                })
            }

        logger.info(f"Invoking agent {BEDROCK_AGENT_ID} with alias {BEDROCK_AGENT_ALIAS_ID}")

        # Invoke Bedrock Agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=input_text,
            enableTrace=enable_trace
        )

        # Process the response stream
        event_stream = response['completion']
        full_response = ""
        trace_data = []

        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    full_response += chunk['bytes'].decode('utf-8')

            if 'trace' in event and enable_trace:
                trace_data.append(event['trace'])

        # Build response
        result = {
            'sessionId': session_id,
            'response': full_response,
            'agentId': BEDROCK_AGENT_ID,
            'agentAliasId': BEDROCK_AGENT_ALIAS_ID
        }

        if enable_trace:
            result['trace'] = trace_data

        logger.info(f"Successfully processed request for session {session_id}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': str(ve)
            })
        }

    except Exception as e:
        logger.error(f"Error invoking Bedrock agent: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Simple health check endpoint for monitoring.
    """
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'healthy',
            'environment': ENVIRONMENT,
            'agentConfigured': bool(BEDROCK_AGENT_ID)
        })
    }
