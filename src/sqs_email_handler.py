import json
import logging
import time
from typing import Dict, Any

# Import services and integrations (three-layer architecture)
from services import email as email_service
from services import s3 as s3_service
from services import prompts as prompt_service
from integrations import agentcore_invocation

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

            # Step 5: Fetch email from S3 using services layer
            logger.info("Fetching email from S3...")
            email_content = s3_service.fetch_email_from_s3(bucket_name, object_key)
            logger.info(f"Fetched {len(email_content):,} bytes from S3")

            # Step 6: Parse email and extract body using services layer
            logger.info("Parsing email...")
            email_body = email_service.extract_email_body(email_content)

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

            # Step 7: Invoke agent to create GitHub issue
            agent_response = None
            # Use text body if available, otherwise HTML, otherwise empty
            body_for_agent = email_body.get('text_body') or email_body.get('html_body') or ""

            try:
                if body_for_agent:
                    logger.info("Invoking Bedrock agent to create GitHub issue from email...")
                    agent_start_time = time.time()

                    # Create prompt for agent to create GitHub issue using MCP tools
                    prompt = create_github_issue_prompt(
                        from_address=from_address,
                        subject=subject,
                        body=body_for_agent,
                        timestamp=timestamp
                    )

                    # Invoke agent using integrations layer
                    # Agent will use its GitHub MCP tool to create the issue
                    agent_response = agentcore_invocation.invoke_agent(
                        prompt=prompt,
                        session_id=None  # New session for each email
                    )

                    agent_time = time.time() - agent_start_time
                    logger.info(
                        f"Agent invocation succeeded: "
                        f"response_length={len(agent_response)}, "
                        f"execution_time={agent_time:.2f}s"
                    )

                else:
                    logger.warning("Email body is empty, skipping agent invocation")

            except agentcore_invocation.ConfigurationError as e:
                logger.error(f"Agent configuration error: {e}")
                agent_response = f"[Configuration Error] {str(e)}"
            except agentcore_invocation.AgentNotFoundException as e:
                logger.error(f"Agent not found: {e}")
                agent_response = f"[Agent Not Found] {str(e)}"
            except agentcore_invocation.ThrottlingException as e:
                logger.warning(f"Agent invocation throttled: {e}")
                agent_response = f"[Throttled] {str(e)}"
            except agentcore_invocation.ValidationException as e:
                logger.error(f"Validation error: {e}")
                agent_response = f"[Validation Error] {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected error during agent invocation: {e}", exc_info=True)
                agent_response = f"[Error] {str(e)}"

            # Step 8: Log the email and agent response
            log_email_processing(
                subject=subject,
                from_address=from_address,
                to_addresses=to_addresses,
                timestamp=timestamp,
                text_body=email_body['text_body'],
                html_body=email_body['html_body'],
                attachments=email_body['attachments'],
                agent_response=agent_response
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


def log_email_processing(
    subject: str,
    from_address: str,
    to_addresses: list,
    timestamp: str,
    text_body: str,
    html_body: str,
    attachments: list,
    agent_response: str
) -> None:
    """
    Log the processed email and agent response.

    The agent (using GitHub MCP tools) handles GitHub issue creation.
    This function only logs the results for monitoring and debugging.

    Args:
        subject: Email subject
        from_address: Sender email
        to_addresses: List of recipients
        timestamp: When email was sent
        text_body: Plain text body
        html_body: HTML body
        attachments: List of attachment metadata
        agent_response: Response from Bedrock agent (includes GitHub issue URL if created)
    """
    logger.info("Logging processed email and agent response...")

    # Use text body if available, otherwise HTML, otherwise empty
    body = text_body or html_body or ""

    if not body:
        logger.warning("Email has no text or HTML body content")

    logger.info("=" * 70)
    logger.info("EMAIL CONTENT & AGENT ANALYSIS")
    logger.info("=" * 70)
    logger.info(f"Subject: {subject}")
    logger.info(f"From: {from_address}")
    logger.info(f"To: {to_addresses}")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Attachments: {len(attachments)}")
    if body:
        logger.info(f"Body: {body[:300]}{'...' if len(body) > 300 else ''}")
    else:
        logger.info("Body: (empty)")

    if agent_response:
        logger.info("")
        logger.info("AGENT RESPONSE (GitHub issue created by agent):")
        logger.info("-" * 70)
        logger.info(agent_response)
        logger.info("-" * 70)
    else:
        logger.info("")
        logger.info("AGENT RESPONSE: (not available)")

    logger.info("=" * 70)
    logger.info("Email processing completed")
    logger.info("NOTE: GitHub issue creation is handled by the agent's MCP tools")


# Helper functions for GitHub issue creation
# ============================================

def create_github_issue_prompt(
    from_address: str,
    subject: str,
    body: str,
    timestamp: str,
    repository: str = "bugs"
) -> str:
    """
    Create the prompt for the AI agent to analyze the email and create a GitHub issue using MCP tools.

    Loads prompt template from S3 (cached after first load) and formats with email data.

    This prompt instructs the agent to:
    1. Query knowledge base for the GitHub bug issue template
    2. Extract relevant information from the customer email based on template structure
    3. Format the issue body according to the template
    4. Use GitHub MCP tools to create the issue directly
    5. Return confirmation with the issue URL

    Args:
        from_address: Email sender
        subject: Email subject line
        body: Email body content
        timestamp: When the email was received
        repository: Target GitHub repository name (default: "bugs")

    Returns:
        str: Formatted prompt for the AI agent

    Raises:
        ValueError: If prompt template not found in S3
    """
    # Load prompt template from S3 (cached on warm invocations)
    prompt_template = prompt_service.load_prompt("github_issue.txt")

    # Format with email data
    prompt = prompt_service.format_prompt(
        prompt_template,
        from_address=from_address,
        subject=subject,
        body=body,
        timestamp=timestamp,
        repository=repository
    )

    return prompt


# Additional helper functions
# ============================

def save_to_dynamodb(email_data: dict) -> None:
    """Save email to DynamoDB table."""
    # dynamodb = boto3.resource('dynamodb')
    # table = dynamodb.Table('Emails')
    # table.put_item(Item=email_data)
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