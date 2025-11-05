import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from sqs_email_handler import (
    lambda_handler,
    fetch_email_from_s3,
    extract_email_body,
    process_email
)


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

    @patch('sqs_email_handler.s3_client')
    def test_lambda_handler_success(self, mock_s3_client, sqs_event, mock_context, sample_email_content):
        """Test successful email processing."""
        # Mock S3 get_object
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }

        # Invoke handler
        result = lambda_handler(sqs_event, mock_context)

        # Assertions
        assert result == {"batchItemFailures": []}
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='ses-emails-123456789012-dev',
            Key='test-email-key'
        )

    @patch('sqs_email_handler.s3_client')
    def test_lambda_handler_s3_error(self, mock_s3_client, sqs_event, mock_context):
        """Test handler when S3 fetch fails."""
        # Mock S3 error
        from botocore.exceptions import ClientError
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}},
            'GetObject'
        )

        # Invoke handler
        result = lambda_handler(sqs_event, mock_context)

        # Should report batch item failure
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "test-message-id-123"

    @patch('sqs_email_handler.s3_client')
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
        result = lambda_handler(invalid_event, mock_context)

        # Should report batch item failure
        assert len(result["batchItemFailures"]) == 1


class TestFetchEmailFromS3:
    """Test S3 email fetching."""

    @patch('sqs_email_handler.s3_client')
    def test_fetch_email_success(self, mock_s3_client, sample_email_content):
        """Test successful S3 fetch."""
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email_content)
        }

        result = fetch_email_from_s3('test-bucket', 'test-key')

        assert result == sample_email_content
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test-key'
        )

    @patch('sqs_email_handler.s3_client')
    def test_fetch_email_not_found(self, mock_s3_client):
        """Test S3 fetch when object doesn't exist."""
        from botocore.exceptions import ClientError
        mock_s3_client.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        mock_s3_client.get_object.side_effect = mock_s3_client.exceptions.NoSuchKey()

        with pytest.raises(ValueError, match="Email file not found"):
            fetch_email_from_s3('test-bucket', 'missing-key')


class TestExtractEmailBody:
    """Test email parsing and body extraction."""

    def test_extract_multipart_email(self, sample_email_content):
        """Test extracting body from multipart email."""
        result = extract_email_body(sample_email_content)

        assert 'text_body' in result
        assert 'html_body' in result
        assert 'attachments' in result
        assert 'plain text' in result['text_body']
        assert '<strong>HTML</strong>' in result['html_body']

    def test_extract_simple_text_email(self):
        """Test extracting body from simple text email."""
        simple_email = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Simple Test
Content-Type: text/plain; charset="UTF-8"

Simple email body.
"""
        result = extract_email_body(simple_email)

        assert 'Simple email body' in result['text_body']
        assert result['html_body'] == ''
        assert len(result['attachments']) == 0

    def test_extract_email_with_attachment(self):
        """Test extracting email with attachment."""
        email_with_attachment = b"""From: sender@example.com
To: recipient@yourdomain.com
Subject: Email with Attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary456"

--boundary456
Content-Type: text/plain; charset="UTF-8"

Email body with attachment.

--boundary456
Content-Type: application/pdf; name="document.pdf"
Content-Disposition: attachment; filename="document.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQKJeLjz9MK...

--boundary456--
"""
        result = extract_email_body(email_with_attachment)

        assert 'Email body with attachment' in result['text_body']
        assert len(result['attachments']) == 1
        assert result['attachments'][0]['filename'] == 'document.pdf'
        assert result['attachments'][0]['content_type'] == 'application/pdf'


class TestProcessEmail:
    """Test email processing logic."""

    def test_process_email_with_text_body(self, caplog):
        """Test processing email with text body."""
        process_email(
            subject="Test Subject",
            from_address="sender@example.com",
            to_addresses=["recipient@yourdomain.com"],
            timestamp="2024-11-05T10:30:00.000Z",
            text_body="This is the email body",
            html_body="",
            attachments=[],
            ses_notification={}
        )

        # Check that email was logged
        assert "Processing email body" in caplog.text
        assert "Test Subject" in caplog.text

    def test_process_email_empty_body(self, caplog):
        """Test processing email with empty body."""
        process_email(
            subject="Empty Email",
            from_address="sender@example.com",
            to_addresses=["recipient@yourdomain.com"],
            timestamp="2024-11-05T10:30:00.000Z",
            text_body="",
            html_body="",
            attachments=[],
            ses_notification={}
        )

        # Should warn about empty body
        assert "no text or HTML body content" in caplog.text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
