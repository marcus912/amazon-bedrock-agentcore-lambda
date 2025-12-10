"""
Data models for email processing domain.

These type-safe data structures define clear contracts between components.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Attachment:
    """
    Email attachment with content and optional URL.

    Attributes:
        filename: Original filename
        content_type: MIME type (e.g., "image/png", "application/pdf")
        size: Size in bytes
        content: Binary content (may be None if not extracted)
        url: Public URL after upload (None until uploaded)
    """
    filename: str
    content_type: str
    size: int
    content: Optional[bytes] = None
    url: Optional[str] = None

    @property
    def is_image(self) -> bool:
        """Check if attachment is an image."""
        return self.content_type.lower().startswith('image/')

    def to_dict_for_agent(self) -> Dict[str, Any]:
        """
        Convert to dict format for agent payload.

        Returns:
            Dict with filename, content_type, and url (if available)
        """
        result = {
            'filename': self.filename,
            'content_type': self.content_type,
        }
        if self.url:
            result['url'] = self.url
        return result


@dataclass
class EmailMetadata:
    """
    Structured email metadata extracted from SES notification.

    Attributes:
        message_id: Unique SQS message identifier
        from_address: Email sender address
        to_addresses: List of recipient addresses
        subject: Email subject line
        timestamp: ISO 8601 timestamp when email was received
        bucket_name: S3 bucket containing the raw email
        object_key: S3 object key for the raw email
    """
    message_id: str
    from_address: str
    to_addresses: List[str]
    subject: str
    timestamp: str
    bucket_name: str
    object_key: str


@dataclass
class EmailContent:
    """
    Parsed email content.

    Attributes:
        text_body: Plain text body (empty string if not present)
        html_body: HTML body (empty string if not present)
        attachments: List of Attachment objects
    """
    text_body: str
    html_body: str
    attachments: List[Attachment] = field(default_factory=list)

    @property
    def body_for_agent(self) -> str:
        """
        Get best available body content for agent processing.

        Priority: text_body > html_body > empty string

        Returns:
            str: The email body to send to the agent
        """
        return self.text_body or self.html_body or ""

    @property
    def has_content(self) -> bool:
        """Check if email has any body content."""
        return bool(self.text_body or self.html_body)

    @property
    def attachments_with_urls(self) -> List[Attachment]:
        """Get attachments that have been uploaded and have URLs."""
        return [a for a in self.attachments if a.url]

    def attachments_for_agent(self) -> List[Dict[str, Any]]:
        """
        Get attachments formatted for agent payload.

        Only includes attachments that have URLs.

        Returns:
            List of dicts with filename, content_type, and url
        """
        return [a.to_dict_for_agent() for a in self.attachments_with_urls]


@dataclass
class ProcessingResult:
    """
    Result of email processing operation.

    This explicit result type makes success/failure handling clear
    and prevents exceptions from being used for control flow.

    Attributes:
        success: Whether processing succeeded
        message_id: SQS message identifier
        metadata: Email metadata (if parsing succeeded)
        agent_response: Agent's response (if invocation succeeded)
        error_message: Error description (if processing failed)
    """
    success: bool
    message_id: str
    metadata: Optional[EmailMetadata] = None
    agent_response: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def should_delete_message(self) -> bool:
        """Always True - delete all messages to prevent infinite retries."""
        return True

    def __repr__(self) -> str:
        """Human-readable representation for logging."""
        if self.success:
            return f"ProcessingResult(success=True, message_id={self.message_id})"
        else:
            return f"ProcessingResult(success=False, message_id={self.message_id}, error={self.error_message})"
