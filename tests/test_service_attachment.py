"""
Tests for attachment upload service.
"""

import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))


class TestIsConfigured:
    """Test attachment configuration check."""

    def test_configured_when_both_vars_set(self):
        """Test returns True when both bucket and domain are set."""
        with patch.dict(os.environ, {
            'ATTACHMENTS_S3_BUCKET': 'my-bucket',
            'ATTACHMENTS_CLOUDFRONT_DOMAIN': 'cdn.example.com'
        }):
            # Need to reimport to pick up new env vars
            from services import attachment
            # Force reload module to pick up new env vars
            import importlib
            importlib.reload(attachment)
            assert attachment.is_configured() is True

    def test_not_configured_when_bucket_missing(self):
        """Test returns False when bucket is missing."""
        with patch.dict(os.environ, {
            'ATTACHMENTS_S3_BUCKET': '',
            'ATTACHMENTS_CLOUDFRONT_DOMAIN': 'cdn.example.com'
        }, clear=False):
            from services import attachment
            import importlib
            importlib.reload(attachment)
            assert attachment.is_configured() is False

    def test_not_configured_when_domain_missing(self):
        """Test returns False when domain is missing."""
        with patch.dict(os.environ, {
            'ATTACHMENTS_S3_BUCKET': 'my-bucket',
            'ATTACHMENTS_CLOUDFRONT_DOMAIN': ''
        }, clear=False):
            from services import attachment
            import importlib
            importlib.reload(attachment)
            assert attachment.is_configured() is False


class TestSanitizeForS3Key:
    """Test S3 key sanitization."""

    def test_strips_angle_brackets(self):
        """Test removes angle brackets from message IDs."""
        from services.attachment import _sanitize_for_s3_key
        result = _sanitize_for_s3_key('<abc123@example.com>')
        assert result == 'abc123@example.com'

    def test_replaces_slashes(self):
        """Test replaces forward and back slashes."""
        from services.attachment import _sanitize_for_s3_key
        result = _sanitize_for_s3_key('path/to\\file')
        assert result == 'path_to_file'

    def test_replaces_special_chars(self):
        """Test replaces special characters."""
        from services.attachment import _sanitize_for_s3_key
        result = _sanitize_for_s3_key('file#name?with&special%chars')
        assert result == 'file_name_with_special_chars'

    def test_removes_control_characters(self):
        """Test removes control characters."""
        from services.attachment import _sanitize_for_s3_key
        result = _sanitize_for_s3_key('file\x00name\x1f')
        assert result == 'filename'

    def test_preserves_normal_characters(self):
        """Test preserves normal characters."""
        from services.attachment import _sanitize_for_s3_key
        result = _sanitize_for_s3_key('normal-file_name.txt')
        assert result == 'normal-file_name.txt'


class TestIsImageContentType:
    """Test image content type detection."""

    def test_image_png(self):
        """Test detects PNG as image."""
        from services.attachment import is_image_content_type
        assert is_image_content_type('image/png') is True

    def test_image_jpeg(self):
        """Test detects JPEG as image."""
        from services.attachment import is_image_content_type
        assert is_image_content_type('image/jpeg') is True

    def test_image_gif(self):
        """Test detects GIF as image."""
        from services.attachment import is_image_content_type
        assert is_image_content_type('image/gif') is True

    def test_image_case_insensitive(self):
        """Test detection is case-insensitive."""
        from services.attachment import is_image_content_type
        assert is_image_content_type('IMAGE/PNG') is True
        assert is_image_content_type('Image/Jpeg') is True

    def test_not_image_pdf(self):
        """Test PDF is not detected as image."""
        from services.attachment import is_image_content_type
        assert is_image_content_type('application/pdf') is False

    def test_not_image_text(self):
        """Test text is not detected as image."""
        from services.attachment import is_image_content_type
        assert is_image_content_type('text/plain') is False


class TestUploadAttachment:
    """Test attachment upload functionality."""

    @patch('services.attachment.s3_client')
    @patch('services.attachment.is_configured')
    def test_upload_success(self, mock_is_configured, mock_s3_client):
        """Test successful attachment upload."""
        mock_is_configured.return_value = True
        mock_s3_client.put_object.return_value = {}

        from services import attachment
        # Set module variables for test
        attachment.ATTACHMENTS_BUCKET = 'test-bucket'
        attachment.CLOUDFRONT_DOMAIN = 'cdn.example.com'
        attachment.ENVIRONMENT = 'test'
        attachment.MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

        result = attachment.upload_attachment(
            filename='test.png',
            content=b'fake image content',
            content_type='image/png',
            message_id='<abc123@example.com>'
        )

        assert result == 'https://cdn.example.com/attachments/test/abc123@example.com/test.png'
        mock_s3_client.put_object.assert_called_once()

    @patch('services.attachment.s3_client')
    @patch('services.attachment.is_configured')
    def test_upload_not_configured(self, mock_is_configured, mock_s3_client):
        """Test returns None when not configured."""
        mock_is_configured.return_value = False

        from services import attachment
        result = attachment.upload_attachment(
            filename='test.png',
            content=b'fake image content',
            content_type='image/png',
            message_id='abc123'
        )

        assert result is None
        mock_s3_client.put_object.assert_not_called()

    @patch('services.attachment.s3_client')
    @patch('services.attachment.is_configured')
    def test_upload_file_too_large(self, mock_is_configured, mock_s3_client):
        """Test skips files exceeding size limit."""
        mock_is_configured.return_value = True

        from services import attachment
        attachment.MAX_FILE_SIZE_BYTES = 100  # Set small limit for test

        # Content larger than limit
        large_content = b'X' * 200

        result = attachment.upload_attachment(
            filename='large.png',
            content=large_content,
            content_type='image/png',
            message_id='abc123'
        )

        assert result is None
        mock_s3_client.put_object.assert_not_called()

    @patch('services.attachment.s3_client')
    @patch('services.attachment.is_configured')
    def test_upload_client_error(self, mock_is_configured, mock_s3_client):
        """Test returns None on S3 client error."""
        mock_is_configured.return_value = True
        mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'PutObject'
        )

        from services import attachment
        attachment.ATTACHMENTS_BUCKET = 'test-bucket'
        attachment.CLOUDFRONT_DOMAIN = 'cdn.example.com'
        attachment.ENVIRONMENT = 'test'
        attachment.MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

        result = attachment.upload_attachment(
            filename='test.png',
            content=b'fake content',
            content_type='image/png',
            message_id='abc123'
        )

        assert result is None

    @patch('services.attachment.s3_client')
    @patch('services.attachment.is_configured')
    def test_upload_unexpected_error(self, mock_is_configured, mock_s3_client):
        """Test returns None on unexpected error."""
        mock_is_configured.return_value = True
        mock_s3_client.put_object.side_effect = RuntimeError("Network error")

        from services import attachment
        attachment.ATTACHMENTS_BUCKET = 'test-bucket'
        attachment.CLOUDFRONT_DOMAIN = 'cdn.example.com'
        attachment.ENVIRONMENT = 'test'
        attachment.MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

        result = attachment.upload_attachment(
            filename='test.png',
            content=b'fake content',
            content_type='image/png',
            message_id='abc123'
        )

        assert result is None

    @patch('services.attachment.s3_client')
    @patch('services.attachment.is_configured')
    def test_upload_sanitizes_filename(self, mock_is_configured, mock_s3_client):
        """Test filename is sanitized for S3 key."""
        mock_is_configured.return_value = True
        mock_s3_client.put_object.return_value = {}

        from services import attachment
        attachment.ATTACHMENTS_BUCKET = 'test-bucket'
        attachment.CLOUDFRONT_DOMAIN = 'cdn.example.com'
        attachment.ENVIRONMENT = 'dev'
        attachment.MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

        result = attachment.upload_attachment(
            filename='file/with\\special#chars.png',
            content=b'fake content',
            content_type='image/png',
            message_id='<msg@example.com>'
        )

        # Verify the key was sanitized
        call_args = mock_s3_client.put_object.call_args
        key = call_args[1]['Key']
        assert '/' not in key.split('attachments/dev/')[1].replace('/', '', 1)  # Only path separators, not in filename


class TestAttachmentModel:
    """Test Attachment dataclass from models."""

    def test_attachment_is_image(self):
        """Test is_image property for image content types."""
        from domain.models import Attachment

        img = Attachment(filename='test.png', content_type='image/png', size=100)
        assert img.is_image is True

        pdf = Attachment(filename='doc.pdf', content_type='application/pdf', size=100)
        assert pdf.is_image is False

    def test_attachment_to_dict_for_agent(self):
        """Test to_dict_for_agent method."""
        from domain.models import Attachment

        # Without URL
        att = Attachment(filename='test.png', content_type='image/png', size=100)
        result = att.to_dict_for_agent()
        assert result == {'filename': 'test.png', 'content_type': 'image/png'}

        # With URL
        att.url = 'https://cdn.example.com/test.png'
        result = att.to_dict_for_agent()
        assert result == {
            'filename': 'test.png',
            'content_type': 'image/png',
            'url': 'https://cdn.example.com/test.png'
        }


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
