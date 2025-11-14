"""
Tests for S3 service operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from services import s3


class TestFetchEmailFromS3:
    """Test fetching email content from S3."""

    @patch('services.s3.s3_client')
    def test_fetch_email_success(self, mock_s3_client):
        """Test successful email fetch from S3."""
        # Setup
        sample_email = b"From: test@example.com\r\nSubject: Test\r\n\r\nBody content"
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: sample_email)
        }

        # Execute
        result = s3.fetch_email_from_s3('test-bucket', 'emails/test.eml')

        # Assert
        assert result == sample_email
        assert isinstance(result, bytes)
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='emails/test.eml'
        )

    @patch('services.s3.s3_client')
    def test_fetch_email_no_such_key(self, mock_s3_client):
        """Test fetch when S3 object doesn't exist."""
        # Setup - Create proper exception class that inherits from Exception
        class NoSuchKey(Exception):
            pass

        mock_s3_client.exceptions.NoSuchKey = NoSuchKey
        mock_s3_client.get_object.side_effect = NoSuchKey("Key not found")

        # Execute & Assert
        with pytest.raises(ValueError, match="Email file not found in S3"):
            s3.fetch_email_from_s3('test-bucket', 'missing-email.eml')

    @patch('services.s3.s3_client')
    def test_fetch_email_no_such_bucket(self, mock_s3_client):
        """Test fetch when S3 bucket doesn't exist."""
        # Setup - Create proper exception classes that inherit from Exception
        class NoSuchKey(Exception):
            pass

        class NoSuchBucket(Exception):
            pass

        mock_s3_client.exceptions.NoSuchKey = NoSuchKey
        mock_s3_client.exceptions.NoSuchBucket = NoSuchBucket
        mock_s3_client.get_object.side_effect = NoSuchBucket("Bucket does not exist")

        # Execute & Assert
        with pytest.raises(ValueError, match="S3 bucket not found"):
            s3.fetch_email_from_s3('missing-bucket', 'emails/test.eml')

    @patch('services.s3.s3_client')
    def test_fetch_email_generic_error(self, mock_s3_client):
        """Test fetch with generic S3 error."""
        # Setup - Mock NoSuchKey and NoSuchBucket first so they don't interfere
        class NoSuchKey(Exception):
            pass

        class NoSuchBucket(Exception):
            pass

        mock_s3_client.exceptions.NoSuchKey = NoSuchKey
        mock_s3_client.exceptions.NoSuchBucket = NoSuchBucket

        # Now set the generic exception
        mock_s3_client.get_object.side_effect = RuntimeError("S3 connection error")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="S3 connection error"):
            s3.fetch_email_from_s3('test-bucket', 'emails/test.eml')

    @patch('services.s3.s3_client')
    def test_fetch_large_email(self, mock_s3_client):
        """Test fetching a large email file."""
        # Setup - 1MB email
        large_email = b"X" * (1024 * 1024)
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: large_email)
        }

        # Execute
        result = s3.fetch_email_from_s3('test-bucket', 'emails/large.eml')

        # Assert
        assert len(result) == 1024 * 1024
        assert isinstance(result, bytes)


class TestUploadProcessedResult:
    """Test uploading processed results to S3."""

    @patch('services.s3.s3_client')
    def test_upload_result_success(self, mock_s3_client):
        """Test successful result upload."""
        # Setup
        content = "Agent summary: Email is about product inquiry"
        mock_s3_client.put_object.return_value = {}

        # Execute
        s3.upload_processed_result(
            bucket='results-bucket',
            key='processed/2025/11/12/result.txt',
            content=content
        )

        # Assert
        mock_s3_client.put_object.assert_called_once_with(
            Bucket='results-bucket',
            Key='processed/2025/11/12/result.txt',
            Body=content.encode('utf-8'),
            ContentType='text/plain'
        )

    @patch('services.s3.s3_client')
    def test_upload_result_empty_bucket(self, mock_s3_client):
        """Test upload with empty bucket name."""
        with pytest.raises(ValueError, match="bucket name cannot be empty"):
            s3.upload_processed_result(
                bucket='',
                key='result.txt',
                content='test'
            )

    @patch('services.s3.s3_client')
    def test_upload_result_empty_key(self, mock_s3_client):
        """Test upload with empty key."""
        with pytest.raises(ValueError, match="object key cannot be empty"):
            s3.upload_processed_result(
                bucket='test-bucket',
                key='',
                content='test'
            )

    @patch('services.s3.s3_client')
    def test_upload_result_none_content(self, mock_s3_client):
        """Test upload with None content."""
        with pytest.raises(ValueError, match="Content cannot be None"):
            s3.upload_processed_result(
                bucket='test-bucket',
                key='result.txt',
                content=None
            )

    @patch('services.s3.s3_client')
    def test_upload_result_client_error(self, mock_s3_client):
        """Test upload with ClientError."""
        # Setup
        mock_s3_client.put_object.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'AccessDenied',
                    'Message': 'Access Denied'
                }
            },
            'PutObject'
        )

        # Execute & Assert
        with pytest.raises(ClientError):
            s3.upload_processed_result(
                bucket='test-bucket',
                key='result.txt',
                content='test content'
            )

    @patch('services.s3.s3_client')
    def test_upload_result_unicode_content(self, mock_s3_client):
        """Test upload with Unicode content."""
        # Setup
        content = "Agent summary: 📧 Email about プロダクト 询问"
        mock_s3_client.put_object.return_value = {}

        # Execute
        s3.upload_processed_result(
            bucket='test-bucket',
            key='result.txt',
            content=content
        )

        # Assert
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]['Body'] == content.encode('utf-8')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
