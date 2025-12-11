"""
Email processing utilities for Lambda handlers.

This module provides reusable functions for parsing and extracting information
from email content.
"""

import logging
from email import policy
from email.parser import BytesParser
from email.message import Message
from email import message_from_string
from typing import Dict, Any

logger = logging.getLogger(__name__)


def extract_email_body(email_content: bytes) -> Dict[str, Any]:
    """
    Parse raw email (MIME format) and extract body and attachments.

    Args:
        email_content: Raw email bytes from S3

    Returns:
        Dictionary with text_body, html_body, and attachments

    Example:
        >>> email_bytes = b"From: sender@example.com\\r\\n\\r\\nHello World"
        >>> result = extract_email_body(email_bytes)
        >>> print(result['text_body'])
        "Hello World"
    """
    # Parse the MIME email
    msg = BytesParser(policy=policy.default).parsebytes(email_content)

    result = {
        'text_body': '',
        'html_body': '',
        'attachments': []
    }

    # Extract body parts
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Handle attachments (both "attachment" and "inline" with filename)
            # Images are often sent as "inline" in HTML emails
            if "attachment" in content_disposition or (
                "inline" in content_disposition and part.get_filename()
            ):
                filename = part.get_filename()
                if filename:
                    content = part.get_payload(decode=True) or b''
                    result['attachments'].append({
                        'filename': filename,
                        'content_type': content_type,
                        'size': len(content),
                        'content': content  # Include binary content for upload
                    })
            # Also capture files without Content-Disposition but with a filename
            # (some email clients don't set Content-Disposition for images)
            elif part.get_filename() and content_type.startswith(('image/', 'application/')):
                filename = part.get_filename()
                content = part.get_payload(decode=True) or b''
                result['attachments'].append({
                    'filename': filename,
                    'content_type': content_type,
                    'size': len(content),
                    'content': content
                })

            # Extract text body (skip if already found or if it's part of multipart/alternative container)
            elif content_type == "text/plain" and not result['text_body']:
                try:
                    # get_content() handles quoted-printable, base64, etc automatically
                    result['text_body'] = part.get_content()
                except Exception as e:
                    logger.warning(f"Failed to decode text body with get_content(): {e}")
                    # Fallback: manual decode with get_payload(decode=True)
                    payload = part.get_payload(decode=True)
                    if payload:
                        result['text_body'] = payload.decode('utf-8',
                                                             errors='ignore')

            # Extract HTML body (skip if already found)
            elif content_type == "text/html" and not result['html_body']:
                try:
                    # get_content() handles quoted-printable, base64, etc automatically
                    result['html_body'] = part.get_content()
                except Exception as e:
                    logger.warning(f"Failed to decode HTML body with get_content(): {e}")
                    # Fallback: manual decode with get_payload(decode=True)
                    payload = part.get_payload(decode=True)
                    if payload:
                        result['html_body'] = payload.decode('utf-8',
                                                             errors='ignore')
    else:
        # Non-multipart email (single part)
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            result['text_body'] = msg.get_content()
        elif content_type == "text/html":
            result['html_body'] = msg.get_content()
        else:
            logger.warning(
                f"Unknown content type for non-multipart email: {content_type}. "
                f"Email body will be empty."
            )

    return result


def parse_email_headers(email_content: str) -> Dict[str, str]:
    """
    Parse email headers and return them as a dictionary.

    Args:
        email_content: Raw email content as a string (RFC 822 format)

    Returns:
        dict: Dictionary containing email headers (From, To, Subject, Date, etc.)

    Raises:
        ValueError: If email content is invalid or empty

    Example:
        >>> email_raw = "From: sender@example.com\\nTo: recipient@example.com\\nSubject: Test\\n\\nBody"
        >>> headers = parse_email_headers(email_raw)
        >>> print(headers['From'])
        "sender@example.com"
        >>> print(headers['Subject'])
        "Test"
    """
    if not email_content:
        raise ValueError("Email content cannot be empty")

    try:
        # Parse email using Python's email library
        msg: Message = message_from_string(email_content)

        # Extract common headers
        headers = {
            'From': msg.get('From', ''),
            'To': msg.get('To', ''),
            'Subject': msg.get('Subject', ''),
            'Date': msg.get('Date', ''),
            'Message-ID': msg.get('Message-ID', ''),
            'Reply-To': msg.get('Reply-To', ''),
            'Cc': msg.get('Cc', ''),
            'Bcc': msg.get('Bcc', ''),
        }

        # Remove empty headers
        headers = {k: v for k, v in headers.items() if v}

        logger.info(f"Parsed email headers: {list(headers.keys())}")
        return headers

    except Exception as e:
        logger.error(f"Failed to parse email headers: {e}")
        raise ValueError(f"Failed to parse email headers: {str(e)}")
