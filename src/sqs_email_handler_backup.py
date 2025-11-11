import json
import logging
import boto3
from email import policy
from email.parser import BytesParser
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add console handler for local testing (AWS Lambda provides handlers automatically)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Initialize S3 client
s3_client = boto3.client('s3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler to extract email body from SES notifications in SQS.

    Flow:
    1. Read SQS message containing SES notification
    2. Extract S3 bucket and key from notification
    3. Fetch email file from S3
    4. Parse email and extract body
    5. Process the email body
    """
    logger.info("=" * 70)
    logger.info("Email Body Extractor - Started")
    logger.info("=" * 70)

    batch_item_failures = []

    for record in event.get('Records', []):
        message_id = record.get('messageId', 'UNKNOWN')

        try:
            logger.info(f"Processing SQS message: {message_id}")

            # Step 1: Parse SQS message body
            sqs_body = json.loads(record['body'])

            # Check if this is wrapped in SNS (optional setup: SES -> SNS -> SQS)
            # Your setup: SES -> SQS (direct)
            if sqs_body.get('Type') == 'Notification' and 'Message' in sqs_body:
                logger.info("Unwrapping SNS message (SES -> SNS -> SQS)")
                ses_notification = json.loads(sqs_body['Message'])
            else:
                # Direct SES to SQS (your current setup)
                ses_notification = sqs_body

            # Step 2: Validate SES notification structure
            if 'mail' not in ses_notification or 'receipt' not in ses_notification:
                logger.error(f"Invalid SES notification structure: {json.dumps(ses_notification)[:200]}")
                raise ValueError("SES notification missing 'mail' or 'receipt' fields")

            # Step 3: Extract email metadata from SES notification
            mail = ses_notification.get('mail', {})
            receipt = ses_notification.get('receipt', {})
            common_headers = mail.get('commonHeaders', {})

            subject = common_headers.get('subject', 'No Subject')

            # Handle 'from' field - can be a list or might be in 'returnPath'
            from_field = common_headers.get('from', [])
            if isinstance(from_field, list) and len(from_field) > 0:
                from_address = from_field[0]
            else:
                from_address = common_headers.get('returnPath', 'Unknown')

            to_addresses = common_headers.get('to', [])
            timestamp = mail.get('timestamp', '')

            logger.info(f"Email metadata:")
            logger.info(f"  From: {from_address}")
            logger.info(f"  To: {to_addresses}")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  Timestamp: {timestamp}")

            # Step 4: Extract S3 location from receipt
            action = receipt.get('action', {})
            bucket_name = action.get('bucketName')
            object_key = action.get('objectKey')

            if not bucket_name or not object_key:
                logger.error("S3 bucket or key not found in SES notification")
                raise ValueError("Missing S3 location in SES notification")

            logger.info(f"Email stored at: s3://{bucket_name}/{object_key}")

            # Step 5: Fetch email from S3
            logger.info("Fetching email from S3...")
            email_content = fetch_email_from_s3(bucket_name, object_key)
            logger.info(f"Fetched {len(email_content):,} bytes from S3")

            # Step 6: Parse email and extract body
            logger.info("Parsing email...")
            email_body = extract_email_body(email_content)

            logger.info(f"Email body extracted:")
            logger.info(
                f"  Text body: {len(email_body.get('text_body', ''))} characters")
            logger.info(
                f"  HTML body: {len(email_body.get('html_body', ''))} characters")
            logger.info(f"  Attachments: {len(email_body.get('attachments', []))}")

            # Log body preview
            text_preview = email_body.get('text_body', '')[:200] if email_body.get('text_body') else None
            if text_preview:
                logger.info(f"Body preview: {text_preview}...")

            # Step 7: Process the email
            process_email(
                subject=subject,
                from_address=from_address,
                to_addresses=to_addresses,
                timestamp=timestamp,
                text_body=email_body['text_body'],
                html_body=email_body['html_body'],
                attachments=email_body['attachments'],
                ses_notification=ses_notification
            )

            logger.info(f"✓ Successfully processed message {message_id}")

        except Exception as e:
            logger.error(f"✗ Error processing message {message_id}: {str(e)}",
                         exc_info=True)
            batch_item_failures.append({"itemIdentifier": message_id})

    logger.info("=" * 70)
    logger.info(f"Batch processing complete")
    logger.info("=" * 70)

    return {"batchItemFailures": batch_item_failures}


def fetch_email_from_s3(bucket_name: str, object_key: str) -> bytes:
    """
    Fetch raw email content from S3.

    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key

    Returns:
        Raw email content as bytes
    """
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        return response['Body'].read()
    except s3_client.exceptions.NoSuchKey:
        logger.error(f"S3 object not found: s3://{bucket_name}/{object_key}")
        raise ValueError(f"Email file not found in S3: {object_key}")
    except s3_client.exceptions.NoSuchBucket:
        logger.error(f"S3 bucket not found: {bucket_name}")
        raise ValueError(f"S3 bucket not found: {bucket_name}")
    except Exception as e:
        logger.error(f"Failed to fetch from S3 s3://{bucket_name}/{object_key}: {e}")
        raise


def extract_email_body(email_content: bytes) -> Dict[str, Any]:
    """
    Parse raw email (MIME format) and extract body and attachments.

    Args:
        email_content: Raw email bytes from S3

    Returns:
        Dictionary with text_body, html_body, and attachments
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

            # Handle attachments
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    result['attachments'].append({
                        'filename': filename,
                        'content_type': content_type,
                        'size': len(part.get_payload(decode=True) or b'')
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

    return result


def process_email(
    subject: str,
    from_address: str,
    to_addresses: list,
    timestamp: str,
    text_body: str,
    html_body: str,
    attachments: list,
    ses_notification: dict
) -> None:
    """
    Process the extracted email body.
    Customize this function with your business logic.

    Args:
        subject: Email subject
        from_address: Sender email
        to_addresses: List of recipients
        timestamp: When email was sent
        text_body: Plain text body
        html_body: HTML body
        attachments: List of attachment metadata
        ses_notification: Full SES notification data
    """
    logger.info("Processing email body...")

    # Use text body if available, otherwise HTML, otherwise empty
    body = text_body or html_body or ""

    if not body:
        logger.warning("Email has no text or HTML body content")

    logger.info("=" * 70)
    logger.info("EMAIL CONTENT")
    logger.info("=" * 70)
    logger.info(f"Subject: {subject}")
    logger.info(f"From: {from_address}")
    logger.info(f"To: {to_addresses}")
    logger.info(f"Attachments: {len(attachments)}")
    if body:
        logger.info(f"Body: {body[:500]}{'...' if len(body) > 500 else ''}")
    else:
        logger.info("Body: (empty)")
    logger.info("=" * 70)

    # YOUR BUSINESS LOGIC HERE
    # ==========================

    # Example 1: Save to DynamoDB
    # save_to_dynamodb({
    #     'message_id': ses_notification['mail']['messageId'],
    #     'subject': subject,
    #     'from': from_address,
    #     'to': to_addresses,
    #     'body': body,
    #     'timestamp': timestamp
    # })

    # Example 2: Create support ticket for bug reports
    # if any(keyword in subject.lower() for keyword in ['bug', 'error', 'wrong', 'issue']):
    #     create_support_ticket({
    #         'title': subject,
    #         'description': body,
    #         'reporter': from_address,
    #         'priority': 'medium'
    #     })

    # Example 3: Extract product info (like "pinnacle 2.2, firmware 1.2.3.4")
    # product_info = extract_product_details(body)
    # logger.info(f"Product info: {product_info}")

    # Example 4: Send to Slack
    # send_to_slack(
    #     channel='#support',
    #     message=f"New email from {from_address}: {subject}\n{body[:200]}..."
    # )

    # Example 5: Auto-reply
    # send_auto_reply(from_address, subject)

    logger.info("Email processing completed")


# Helper functions for your business logic
# ==========================================

def save_to_dynamodb(email_data: dict) -> None:
    """Save email to DynamoDB table."""
    # dynamodb = boto3.resource('dynamodb')
    # table = dynamodb.Table('Emails')
    # table.put_item(Item=email_data)
    pass


def create_support_ticket(ticket_data: dict) -> None:
    """Create a support ticket in your system."""
    # Example: Call Jira API, Zendesk, etc.
    pass


def extract_product_details(body: str) -> dict:
    """Extract product and firmware info from email body."""
    import re

    product_info = {}

    # Example: Extract "pinnacle 2.2"
    product_match = re.search(r'pinnacle\s+([\d.]+)', body, re.IGNORECASE)
    if product_match:
        product_info['product'] = f"pinnacle {product_match.group(1)}"

    # Example: Extract "firmware 1.2.3.4"
    firmware_match = re.search(r'firmware\s+([\d.]+)', body, re.IGNORECASE)
    if firmware_match:
        product_info['firmware'] = firmware_match.group(1)

    return product_info


def send_to_slack(channel: str, message: str) -> None:
    """Send notification to Slack."""
    # import requests
    # webhook_url = 'YOUR_SLACK_WEBHOOK_URL'
    # requests.post(webhook_url, json={'channel': channel, 'text': message})
    pass


def send_auto_reply(to_address: str, original_subject: str) -> None:
    """Send auto-reply confirmation email."""
    # ses = boto3.client('ses')
    # ses.send_email(
    #     Source='no-reply@linksys.cloud',
    #     Destination={'ToAddresses': [to_address]},
    #     Message={
    #         'Subject': {'Data': f'Re: {original_subject}'},
    #         'Body': {
    #             'Text': {'Data': 'Thank you for your email. We have received it.'}
    #         }
    #     }
    # )
    pass