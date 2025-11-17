"""
Tests for SQS Email Handler Lambda function.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

# Import the handler and dependencies
import sqs_email_handler
from services import s3 as s3_service
from services import email as email_service


@pytest.fixture
def sqs_event():
    """Load sample SQS event from test data."""
    with open(os.path.join(os.path.dirname(__file__), 'events', 'sqs-event.json')) as f:
        return json.load(f)


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    context = Mock()
    context.request_id = "test-request-id"
    context.invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:test"
    context.function_name = "ses-email-handler-test"
    return context


@pytest.fixture
def sample_email_content():
    """Sample raw email content in MIME format."""
    return b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Test Email Subject
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="UTF-8"

This is a test email body in plain text.

--boundary123
Content-Type: text/html; charset="UTF-8"

<html><body><p>This is a test email body in <strong>HTML</strong>.</p></body></html>

--boundary123--
"""


class TestLambdaHandler:
    """Test the main Lambda handler function."""

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_lambda_handler_success(self, mock_bedrock_client, mock_s3_client, sqs_event, mock_context, sample_email_content):
        """Test successful email processing."""
        # Mock S3 get_object
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }

        # Mock Bedrock agent response
        mock_bedrock_client.invoke_agent.return_value = {
            'response': MagicMock(
                read=lambda: json.dumps({'output': 'Agent summary of the email'}).encode('utf-8')
            )
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(sqs_event, mock_context)

        # Assertions
        assert result == {"batchItemFailures": []}
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='ses-emails-123456789012-dev',
            Key='test-email-key'
        )
        mock_bedrock_client.invoke_agent.assert_called_once()

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    def test_lambda_handler_s3_error(self, mock_s3_client, sqs_event, mock_context):
        """Test handler when S3 fetch fails."""
        # Mock S3 error
        from botocore.exceptions import ClientError
        mock_s3_client.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        mock_s3_client.get_object.side_effect = mock_s3_client.exceptions.NoSuchKey()

        # Invoke handler
        result = sqs_email_handler.lambda_handler(sqs_event, mock_context)

        # Should report batch item failure
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "test-message-id-123"

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    def test_lambda_handler_invalid_ses_notification(self, mock_s3_client, mock_context):
        """Test handler with invalid SES notification."""
        # Create invalid event
        invalid_event = {
            "Records": [{
                "messageId": "test-message-id",
                "body": json.dumps({"invalid": "data"})
            }]
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(invalid_event, mock_context)

        # Should report batch item failure
        assert len(result["batchItemFailures"]) == 1

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_lambda_handler_agent_failure(self, mock_bedrock_client, mock_s3_client, sqs_event, mock_context, sample_email_content):
        """Test handler when agent invocation fails."""
        # Mock S3 success
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }

        # Mock Bedrock agent failure
        from botocore.exceptions import ClientError
        mock_bedrock_client.invoke_agent.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
            'InvokeAgentRuntime'
        )

        # Invoke handler - should not fail, agent error should be caught
        result = sqs_email_handler.lambda_handler(sqs_event, mock_context)

        # Should still succeed (agent errors are logged but not propagated)
        assert result == {"batchItemFailures": []}

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_lambda_handler_multiple_records(self, mock_bedrock_client, mock_s3_client, mock_context, sample_email_content):
        """Test handler with multiple SQS records."""
        # Create event with 3 records
        multi_event = {
            "Records": [
                {
                    "messageId": f"msg-{i}",
                    "body": json.dumps({
                        "notificationType": "Received",
                        "mail": {
                            "commonHeaders": {
                                "from": ["sender@example.com"],
                                "to": ["recipient@example.com"],
                                "subject": f"Email {i}"
                            },
                            "timestamp": "2024-11-05T10:30:00.000Z"
                        },
                        "receipt": {
                            "action": {
                                "type": "S3",
                                "bucketName": "test-bucket",
                                "objectKey": f"email-{i}.eml"
                            }
                        }
                    })
                }
                for i in range(3)
            ]
        }

        # Mock S3 and Bedrock
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }
        mock_bedrock_client.invoke_agent.return_value = {
            'response': MagicMock(
                read=lambda: json.dumps({'output': 'Summary'}).encode('utf-8')
            )
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(multi_event, mock_context)

        # All should succeed
        assert result == {"batchItemFailures": []}
        assert mock_s3_client.get_object.call_count == 3
        assert mock_bedrock_client.invoke_agent.call_count == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
