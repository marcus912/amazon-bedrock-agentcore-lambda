"""
S3 operations utilities for Lambda handlers.

This module provides reusable functions for interacting with Amazon S3.
"""

import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configure S3 client with timeouts to prevent infinite hangs
s3_config = Config(
    retries={
        'max_attempts': 1,  # 1 attempt total (no retries)
        'mode': 'standard'
    },
    connect_timeout=10,  # 10 seconds to establish connection
    read_timeout=60      # 60 seconds max for reading response
)

# Initialize S3 client at module level (thread-safe, reused across invocations)
s3_client = boto3.client('s3', config=s3_config)
logger.info("S3 client initialized with timeouts: connect=10s, read=60s, max_attempts=1")


def fetch_email_from_s3(bucket: str, key: str) -> bytes:
    """
    Fetch raw email content from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path to the email file)

    Returns:
        bytes: The raw email content as bytes

    Raises:
        ValueError: If S3 operation fails or bucket/key is invalid

    Example:
        >>> email_bytes = fetch_email_from_s3(
        ...     bucket="my-ses-bucket",
        ...     key="emails/2025/11/12/message-id.eml"
        ... )
        >>> print(len(email_bytes))
        12345
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'NoSuchKey':
            logger.error(f"S3 object not found: s3://{bucket}/{key}")
            raise ValueError(f"Email file not found in S3: {key}")
        elif error_code == 'NoSuchBucket':
            logger.error(f"S3 bucket not found: {bucket}")
            raise ValueError(f"S3 bucket not found: {bucket}")
        else:
            logger.error(f"Failed to fetch from S3 s3://{bucket}/{key}: {e}")
            raise
    except Exception as e:
        logger.error(f"Failed to fetch from S3 s3://{bucket}/{key}: {e}")
        raise


def upload_processed_result(bucket: str, key: str, content: str) -> None:
    """
    Upload processed result to S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path where to upload the file)
        content: Content to upload as a string

    Raises:
        ClientError: If S3 operation fails
        ValueError: If parameters are invalid

    Example:
        >>> result = "Agent summary: The email discusses..."
        >>> upload_processed_result(
        ...     bucket="my-results-bucket",
        ...     key="processed/2025/11/12/result.txt",
        ...     content=result
        ... )
    """
    if not bucket:
        raise ValueError("S3 bucket name cannot be empty")
    if not key:
        raise ValueError("S3 object key cannot be empty")
    if content is None:
        raise ValueError("Content cannot be None")

    try:
        logger.info(
            f"Uploading result to S3: bucket={bucket}, key={key}, "
            f"size={len(content)} bytes"
        )

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='text/plain'
        )

        logger.info(f"Successfully uploaded result to S3: bucket={bucket}, key={key}")

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))

        logger.error(
            f"Failed to upload result to S3: "
            f"bucket={bucket}, key={key}, "
            f"error_code={error_code}, error_message={error_message}"
        )

        raise
