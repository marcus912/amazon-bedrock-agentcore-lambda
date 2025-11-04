import json
import pytest
import os
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.request_id = "test-request-id"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    return context


@pytest.fixture
def mock_env():
    """Set up environment variables."""
    os.environ['BEDROCK_AGENT_ID'] = 'test-agent-id'
    os.environ['BEDROCK_AGENT_ALIAS_ID'] = 'TSTALIASID'
    os.environ['ENVIRONMENT'] = 'test'


def test_lambda_handler_success(lambda_context, mock_env):
    """Test successful Lambda invocation."""
    from src.handler import lambda_handler

    # Mock Bedrock client
    with patch('src.handler.bedrock_agent_runtime') as mock_bedrock:
        # Mock the response stream
        mock_chunk = {
            'chunk': {
                'bytes': b'Test response from Bedrock'
            }
        }
        mock_bedrock.invoke_agent.return_value = {
            'completion': [mock_chunk]
        }

        event = {
            'sessionId': 'test-session',
            'inputText': 'Hello Bedrock',
            'enableTrace': False
        }

        response = lambda_handler(event, lambda_context)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'response' in body
        assert body['sessionId'] == 'test-session'


def test_lambda_handler_missing_input_text(lambda_context, mock_env):
    """Test Lambda with missing input text."""
    from src.handler import lambda_handler

    event = {
        'sessionId': 'test-session'
    }

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'error' in body


def test_lambda_handler_missing_agent_id(lambda_context):
    """Test Lambda with missing agent ID."""
    from src.handler import lambda_handler

    os.environ.pop('BEDROCK_AGENT_ID', None)

    event = {
        'sessionId': 'test-session',
        'inputText': 'Hello'
    }

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 400


def test_health_check(lambda_context, mock_env):
    """Test health check endpoint."""
    from src.handler import health_check

    response = health_check({}, lambda_context)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'healthy'
    assert body['agentConfigured'] is True
