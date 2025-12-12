"""
Email processing pipeline - core business logic.

This module handles the end-to-end processing of SES email notifications:
1. Parse SES notification from SQS record
2. Fetch email from S3
3. Extract email content
4. Invoke Bedrock agent to create GitHub issue
5. Return result (success or failure)

All errors are caught and returned as ProcessingResult with success=False.
No exceptions propagate out of the public methods.
"""

import json
import logging
import time
from typing import Dict, Any

from .models import EmailMetadata, EmailContent, ProcessingResult, Attachment
from services import email as email_service
from services import s3 as s3_service
from services import prompts as prompt_service
from services import attachment as attachment_service
from integrations import agentcore_invocation

logger = logging.getLogger(__name__)


class EmailProcessor:
    """
    Handles end-to-end email processing pipeline.

    Processes SES email notifications and invokes Bedrock agent to create
    GitHub issues. Returns ProcessingResult for explicit success/failure handling.
    """

    def __init__(self):
        """Initialize email processor."""
        pass

    def process_ses_record(self, record: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single SQS record containing SES notification.

        Args:
            record: SQS record dict containing SES notification

        Returns:
            ProcessingResult with success=True or success=False (errors logged)
        """
        message_id = record.get('messageId', 'UNKNOWN')
        logger.info(f"Processing SQS message: {message_id}")

        try:
            metadata = self._parse_ses_notification(record)
            logger.info(f"Parsed: from={metadata.from_address}, subject={metadata.subject}")

            email_content = self._fetch_email(metadata)
            logger.info(
                f"Fetched: text={len(email_content.text_body)}, "
                f"html={len(email_content.html_body)}, attachments={len(email_content.attachments)}"
            )

            # Upload attachments to S3 (if configured)
            self._upload_attachments(metadata, email_content)

            agent_response = self._invoke_agent(metadata, email_content)
            logger.info(f"Agent response: {agent_response[:200]}..." if len(agent_response) > 200 else f"Agent response: {agent_response}")

            self._log_processing_success(metadata, email_content, agent_response)

            return ProcessingResult(
                success=True,
                message_id=message_id,
                metadata=metadata,
                agent_response=agent_response
            )

        except Exception as e:
            logger.error(f"Failed to process {message_id}: {e}", exc_info=True)

            return ProcessingResult(
                success=False,
                message_id=message_id,
                error_message=str(e)
            )

    def _parse_ses_notification(self, record: Dict[str, Any]) -> EmailMetadata:
        """
        Parse SQS record and extract SES notification metadata.

        Handles both direct SES->SQS and SNS-wrapped notifications.

        Args:
            record: SQS record dict

        Returns:
            EmailMetadata: Structured email metadata

        Raises:
            ValueError: If notification structure is invalid
            json.JSONDecodeError: If JSON parsing fails
        """
        message_id = record.get('messageId', 'UNKNOWN')

        # Parse SQS body
        sqs_body = json.loads(record['body'])

        # Check if wrapped in SNS (optional setup: SES -> SNS -> SQS)
        if sqs_body.get('Type') == 'Notification' and 'Message' in sqs_body:
            logger.info("Unwrapping SNS message (SES -> SNS -> SQS)")
            ses_notification = json.loads(sqs_body['Message'])
        else:
            # Direct SES to SQS (standard setup)
            ses_notification = sqs_body

        # Validate SES notification structure
        if 'mail' not in ses_notification or 'receipt' not in ses_notification:
            raise ValueError("SES notification missing 'mail' or 'receipt' fields")

        # Extract email metadata
        mail = ses_notification['mail']
        receipt = ses_notification['receipt']
        common_headers = mail.get('commonHeaders', {})

        # Extract from address (can be list, string, or fallback to returnPath)
        from_field = common_headers.get('from', [])
        if isinstance(from_field, list) and len(from_field) > 0:
            from_address = from_field[0]
        elif isinstance(from_field, str) and from_field:
            # Handle case where 'from' is a string instead of list
            from_address = from_field
        else:
            # Fallback to returnPath from mail object (not commonHeaders)
            from_address = mail.get('returnPath', 'Unknown')

        # Extract to addresses (can be list or string, normalize to list)
        to_field = common_headers.get('to', [])
        if isinstance(to_field, list):
            to_addresses = to_field
        elif isinstance(to_field, str) and to_field:
            # Handle case where 'to' is a string instead of list
            to_addresses = [to_field]
        else:
            to_addresses = []

        # Extract S3 location
        action = receipt.get('action', {})
        bucket_name = action.get('bucketName')
        object_key = action.get('objectKey')

        if not bucket_name or not object_key:
            raise ValueError("Missing S3 location in SES notification")

        return EmailMetadata(
            message_id=message_id,
            from_address=from_address,
            to_addresses=to_addresses,
            subject=common_headers.get('subject', 'No Subject'),
            timestamp=mail.get('timestamp', ''),
            bucket_name=bucket_name,
            object_key=object_key
        )

    def _fetch_email(self, metadata: EmailMetadata) -> EmailContent:
        """
        Fetch email from S3 and parse content.

        Args:
            metadata: Email metadata containing S3 location

        Returns:
            EmailContent: Parsed email content

        Raises:
            ValueError: If S3 fetch fails or email parsing fails
        """
        logger.info(f"Fetching email from: s3://{metadata.bucket_name}/{metadata.object_key}")

        # Fetch raw email from S3
        raw_email = s3_service.fetch_email_from_s3(
            metadata.bucket_name,
            metadata.object_key
        )
        logger.info(f"Fetched {len(raw_email):,} bytes from S3")

        # Parse email content
        parsed = email_service.extract_email_body(raw_email)

        # Convert attachment dicts to Attachment objects
        attachments = [
            Attachment(
                filename=att.get('filename', ''),
                content_type=att.get('content_type', 'application/octet-stream'),
                size=att.get('size', 0),
                content=att.get('content')
            )
            for att in parsed.get('attachments', [])
        ]

        return EmailContent(
            text_body=parsed.get('text_body', ''),
            html_body=parsed.get('html_body', ''),
            attachments=attachments
        )

    def _upload_attachments(
        self,
        metadata: EmailMetadata,
        content: EmailContent
    ) -> None:
        """
        Upload email attachments to S3 and set URLs on Attachment objects.

        Args:
            metadata: Email metadata (for message ID)
            content: Email content with attachments to upload

        Note:
            - Modifies Attachment objects in place to set their URLs
            - Skips if attachment service is not configured
            - Individual upload failures are logged but don't stop processing
        """
        if not attachment_service.is_configured():
            logger.info("Attachment upload not configured, skipping")
            return

        if not content.attachments:
            logger.info("No attachments to upload")
            return

        logger.info(f"Uploading {len(content.attachments)} attachment(s)...")

        uploaded_count = 0
        for attachment in content.attachments:
            if attachment.content is None:
                logger.warning(f"Attachment {attachment.filename} has no content, skipping")
                continue

            url = attachment_service.upload_attachment(
                filename=attachment.filename,
                content=attachment.content,
                content_type=attachment.content_type,
                message_id=metadata.message_id
            )

            if url:
                attachment.url = url
                uploaded_count += 1
                # Clear content after upload to free memory
                attachment.content = None

        logger.info(f"Uploaded {uploaded_count}/{len(content.attachments)} attachment(s)")

    def _invoke_agent(
        self,
        metadata: EmailMetadata,
        content: EmailContent
    ) -> str:
        """
        Invoke Bedrock agent to create GitHub issue from email.

        Args:
            metadata: Email metadata
            content: Parsed email content

        Returns:
            str: Agent's response text

        Raises:
            Various exceptions from agent invocation (caught by caller)
        """
        # Check if email has content
        if not content.has_content:
            logger.warning("Email body is empty, skipping agent invocation")
            return "[Skipped] Email body is empty"

        logger.info("Invoking Bedrock agent to create GitHub issue from email...")
        agent_start_time = time.time()

        # Load and format prompt template
        prompt = self._create_github_issue_prompt(metadata, content)

        # Invoke agent (synchronous - waits for response)
        agent_response = agentcore_invocation.invoke_agent(
            prompt=prompt,
            session_id=None  # New session for each email
        )

        agent_time = time.time() - agent_start_time
        logger.info(f"Agent invocation completed: {agent_time:.3f}s")

        return agent_response

    def _create_github_issue_prompt(
        self,
        metadata: EmailMetadata,
        content: EmailContent
    ) -> str:
        """
        Create prompt for AI agent to create GitHub issue.

        Loads prompt template from S3/filesystem (cached) and formats
        with email data.

        Args:
            metadata: Email metadata
            content: Email content

        Returns:
            str: Formatted prompt for agent

        Raises:
            ValueError: If prompt template not found
        """
        # Load prompt template (cached on warm invocations)
        prompt_template = prompt_service.load_prompt("github_issue.txt")

        # Format attachments for prompt
        attachments_list = content.attachments_for_agent()
        if attachments_list:
            attachments_text = "\n".join(
                f"- {att['filename']} ({att['content_type']}): {att.get('url', 'No URL')}"
                for att in attachments_list
            )
        else:
            attachments_text = "None"

        # Format with email data
        prompt = prompt_service.format_prompt(
            prompt_template,
            from_address=metadata.from_address,
            subject=metadata.subject,
            body=content.body_for_agent,
            timestamp=metadata.timestamp,
            attachments=attachments_text
        )

        return prompt

    def _log_processing_success(
        self,
        metadata: EmailMetadata,
        content: EmailContent,
        agent_response: str
    ) -> None:
        """Log successful processing summary."""
        logger.info("=" * 50)
        logger.info("EMAIL PROCESSED SUCCESSFULLY")
        logger.info(f"From: {metadata.from_address}")
        logger.info(f"Subject: {metadata.subject}")
        logger.info(f"Attachments: {len(content.attachments)}")

        body = content.body_for_agent
        if body:
            preview = body[:200] + ('...' if len(body) > 200 else '')
            logger.info(f"Body preview: {preview}")

        logger.info(f"Agent: {agent_response}")
        logger.info("=" * 50)
