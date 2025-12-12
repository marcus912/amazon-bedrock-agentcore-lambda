"""
Attachment upload service for email attachments.

This module handles uploading email attachments to S3 and generating
public URLs via CloudFront for use in GitHub issues.
"""

import os
import logging
import re
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configure S3 client with timeouts
s3_config = Config(
    retries={
        'max_attempts': 1,
        'mode': 'standard'
    },
    connect_timeout=10,
    read_timeout=60
)

# Module-level client (reused across invocations)
s3_client = boto3.client('s3', config=s3_config)

# Configuration from environment
ATTACHMENTS_BUCKET = os.environ.get('ATTACHMENTS_S3_BUCKET', '')
CLOUDFRONT_DOMAIN = os.environ.get('ATTACHMENTS_CLOUDFRONT_DOMAIN', '')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# File size limits (default: 20 MB)
DEFAULT_MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = int(os.environ.get('ATTACHMENT_MAX_SIZE_MB', DEFAULT_MAX_FILE_SIZE_MB)) * 1024 * 1024


def is_configured() -> bool:
    """
    Check if attachment upload is configured.

    Returns:
        True if both bucket and CloudFront domain are set
    """
    return bool(ATTACHMENTS_BUCKET and CLOUDFRONT_DOMAIN)


def upload_attachment(
    filename: str,
    content: bytes,
    content_type: str,
    message_id: str
) -> Optional[str]:
    """
    Upload attachment to S3 and return public CloudFront URL.

    Args:
        filename: Original filename
        content: Binary content
        content_type: MIME type (e.g., "image/png", "application/pdf")
        message_id: Email message ID (for unique path)

    Returns:
        Public URL via CloudFront, or None if upload fails/skipped

    Note:
        - Files exceeding MAX_FILE_SIZE_BYTES are skipped
        - Upload failures are logged but don't raise exceptions
    """
    if not is_configured():
        logger.warning("Attachment upload not configured (missing env vars)")
        return None

    # Check file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        logger.warning(
            f"Attachment too large, skipping: {filename} "
            f"({len(content):,} bytes > {MAX_FILE_SIZE_BYTES:,} limit)"
        )
        return None

    # Sanitize for S3 key
    safe_message_id = _sanitize_for_s3_key(message_id)
    safe_filename = _sanitize_for_s3_key(filename)

    # Include environment in path: attachments/{env}/{message_id}/{filename}
    key = f"attachments/{ENVIRONMENT}/{safe_message_id}/{safe_filename}"

    try:
        s3_client.put_object(
            Bucket=ATTACHMENTS_BUCKET,
            Key=key,
            Body=content,
            ContentType=content_type
        )

        url = f"https://{CLOUDFRONT_DOMAIN}/{key}"
        logger.info(f"Uploaded attachment: {filename} -> {url}")

        return url

    except ClientError as e:
        logger.error(f"Failed to upload attachment {filename}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading attachment {filename}: {e}")
        return None


def _sanitize_for_s3_key(value: str) -> str:
    """
    Sanitize a string for use in S3 object keys.

    Removes/replaces characters that are problematic in S3 keys or URLs.

    Args:
        value: String to sanitize

    Returns:
        Sanitized string safe for S3 keys
    """
    # Remove angle brackets common in Message-IDs: <abc@example.com>
    result = value.strip('<>')

    # Replace problematic characters
    result = re.sub(r'[/\\#?&%]', '_', result)

    # Remove any remaining control characters
    result = re.sub(r'[\x00-\x1f\x7f]', '', result)

    return result


def is_image_content_type(content_type: str) -> bool:
    """
    Check if content type is an image.

    Args:
        content_type: MIME type string

    Returns:
        True if content type starts with 'image/'
    """
    return content_type.lower().startswith('image/')
