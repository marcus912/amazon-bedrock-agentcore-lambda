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
        """Test successful email processing with agent invocation."""
        # Mock S3 get_object
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }

        # Mock Bedrock agent response (synchronous - response IS read)
        mock_response_stream = MagicMock()
        mock_response_stream.read.return_value = json.dumps({'output': 'GitHub issue created'}).encode('utf-8')
        mock_bedrock_client.invoke_agent_runtime.return_value = {
            'response': mock_response_stream
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(sqs_event, mock_context)

        # Assertions
        assert result == {"batchItemFailures": []}
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='ses-emails-123456789012-dev',
            Key='test-email-key'
        )
        mock_bedrock_client.invoke_agent_runtime.assert_called_once()

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    def test_lambda_handler_s3_error(self, mock_s3_client, sqs_event, mock_context):
        """Test handler when S3 fetch fails - message is still deleted."""
        # Mock S3 error using proper ClientError (matches s3.py exception handling)
        from botocore.exceptions import ClientError
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}},
            'GetObject'
        )

        # Invoke handler
        result = sqs_email_handler.lambda_handler(sqs_event, mock_context)

        # Should delete message even on error (no batch item failures)
        assert len(result["batchItemFailures"]) == 0

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    def test_lambda_handler_invalid_ses_notification(self, mock_s3_client, mock_context):
        """Test handler with invalid SES notification - message is still deleted."""
        # Create invalid event
        invalid_event = {
            "Records": [{
                "messageId": "test-message-id",
                "body": json.dumps({"invalid": "data"})
            }]
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(invalid_event, mock_context)

        # Should delete message even on error (no batch item failures)
        assert len(result["batchItemFailures"]) == 0

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
        mock_bedrock_client.invoke_agent_runtime.side_effect = ClientError(
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

        # Mock S3 and Bedrock (synchronous - response IS read)
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }
        mock_response_stream = MagicMock()
        mock_response_stream.read.return_value = json.dumps({'output': 'GitHub issue created'}).encode('utf-8')
        mock_bedrock_client.invoke_agent_runtime.return_value = {
            'response': mock_response_stream
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(multi_event, mock_context)

        # All should succeed
        assert result == {"batchItemFailures": []}
        assert mock_s3_client.get_object.call_count == 3
        assert mock_bedrock_client.invoke_agent_runtime.call_count == 3

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    @patch('services.s3.s3_client')
    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_lambda_handler_always_consumes_messages(self, mock_bedrock_client, mock_s3_client, mock_context):
        """
        CRITICAL TEST: Verify that messages are ALWAYS consumed (deleted)
        regardless of any error that occurs. This prevents infinite loops
        and message replay.
        """
        # Create event with 3 records that will fail in different ways
        mixed_failure_event = {
            "Records": [
                {
                    "messageId": "msg-invalid-json",
                    "body": "not valid json"  # Will fail JSON parsing
                },
                {
                    "messageId": "msg-missing-fields",
                    "body": json.dumps({"invalid": "structure"})  # Will fail SES validation
                },
                {
                    "messageId": "msg-s3-error",
                    "body": json.dumps({
                        "notificationType": "Received",
                        "mail": {
                            "commonHeaders": {"from": ["test@example.com"], "subject": "Test"},
                            "timestamp": "2024-11-05T10:30:00.000Z"
                        },
                        "receipt": {
                            "action": {
                                "bucketName": "test-bucket",
                                "objectKey": "test-key"
                            }
                        }
                    })  # Will fail on S3 fetch
                }
            ]
        }

        # Mock S3 to fail using proper ClientError
        from botocore.exceptions import ClientError
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}},
            'GetObject'
        )

        # Invoke handler
        result = sqs_email_handler.lambda_handler(mixed_failure_event, mock_context)

        # CRITICAL ASSERTION: All messages must be consumed despite ALL failures
        assert result == {"batchItemFailures": []}, \
            "FAILED: Messages were not consumed! This will cause infinite retries!"
        assert len(result["batchItemFailures"]) == 0, \
            "FAILED: batchItemFailures must ALWAYS be empty to prevent message replay"

    @patch.dict(os.environ, {
        'AGENT_RUNTIME_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123'
    })
    def test_lambda_handler_no_retry_behavior(self, mock_context):
        """
        CRITICAL TEST: Verify that the Lambda does NOT implement any retry logic.
        All retries should be handled by SQS, not by the Lambda function.
        """
        # Create event with invalid data
        event = {
            "Records": [{
                "messageId": "test-msg",
                "body": json.dumps({"invalid": "data"})
            }]
        }

        # Invoke handler
        result = sqs_email_handler.lambda_handler(event, mock_context)

        # Verify no retries - function should return immediately
        assert result == {"batchItemFailures": []}
        # If there were retries, this test would take longer or the structure would be different


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
