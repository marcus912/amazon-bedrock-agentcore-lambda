"""
Tests for domain models (data structures).
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from domain.models import EmailMetadata, EmailContent, ProcessingResult


class TestEmailMetadata:
    """Test EmailMetadata dataclass."""

    def test_email_metadata_creation(self):
        """Test creating EmailMetadata instance."""
        metadata = EmailMetadata(
            message_id="msg-123",
            from_address="sender@example.com",
            to_addresses=["recipient@example.com"],
            subject="Test Subject",
            timestamp="2025-01-01T00:00:00Z",
            bucket_name="test-bucket",
            object_key="test-key"
        )

        assert metadata.message_id == "msg-123"
        assert metadata.from_address == "sender@example.com"
        assert metadata.to_addresses == ["recipient@example.com"]
        assert metadata.subject == "Test Subject"
        assert metadata.timestamp == "2025-01-01T00:00:00Z"
        assert metadata.bucket_name == "test-bucket"
        assert metadata.object_key == "test-key"


class TestEmailContent:
    """Test EmailContent dataclass."""

    def test_email_content_with_text_body(self):
        """Test EmailContent with text body."""
        content = EmailContent(
            text_body="Hello world",
            html_body="",
            attachments=[]
        )

        assert content.text_body == "Hello world"
        assert content.html_body == ""
        assert content.attachments == []
        assert content.body_for_agent == "Hello world"
        assert content.has_content is True

    def test_email_content_with_html_body(self):
        """Test EmailContent with HTML body only."""
        content = EmailContent(
            text_body="",
            html_body="<p>Hello world</p>",
            attachments=[]
        )

        assert content.body_for_agent == "<p>Hello world</p>"
        assert content.has_content is True

    def test_email_content_priority(self):
        """Test body_for_agent prioritizes text over HTML."""
        content = EmailContent(
            text_body="Text version",
            html_body="<p>HTML version</p>",
            attachments=[]
        )

        assert content.body_for_agent == "Text version"

    def test_email_content_empty(self):
        """Test EmailContent with no body."""
        content = EmailContent(
            text_body="",
            html_body="",
            attachments=[]
        )

        assert content.body_for_agent == ""
        assert content.has_content is False

    def test_email_content_with_attachments(self):
        """Test EmailContent with attachments."""
        content = EmailContent(
            text_body="Hello",
            html_body="",
            attachments=[
                {"filename": "test.pdf", "size": 1024},
                {"filename": "image.png", "size": 2048}
            ]
        )

        assert len(content.attachments) == 2
        assert content.attachments[0]["filename"] == "test.pdf"


class TestProcessingResult:
    """Test ProcessingResult dataclass."""

    def test_processing_result_success(self):
        """Test successful ProcessingResult."""
        metadata = EmailMetadata(
            message_id="msg-123",
            from_address="sender@example.com",
            to_addresses=["recipient@example.com"],
            subject="Test",
            timestamp="2025-01-01T00:00:00Z",
            bucket_name="bucket",
            object_key="key"
        )

        result = ProcessingResult(
            success=True,
            message_id="msg-123",
            metadata=metadata,
            agent_response="Issue created: #123"
        )

        assert result.success is True
        assert result.message_id == "msg-123"
        assert result.metadata == metadata
        assert result.agent_response == "Issue created: #123"
        assert result.error_message is None
        assert result.should_delete_message is True

    def test_processing_result_failure(self):
        """Test failed ProcessingResult."""
        result = ProcessingResult(
            success=False,
            message_id="msg-456",
            error_message="S3 fetch failed"
        )

        assert result.success is False
        assert result.message_id == "msg-456"
        assert result.metadata is None
        assert result.agent_response is None
        assert result.error_message == "S3 fetch failed"
        assert result.should_delete_message is True  # Policy: always delete

    def test_processing_result_repr_success(self):
        """Test __repr__ for successful result."""
        result = ProcessingResult(
            success=True,
            message_id="msg-123"
        )

        repr_str = repr(result)
        assert "success=True" in repr_str
        assert "msg-123" in repr_str

    def test_processing_result_repr_failure(self):
        """Test __repr__ for failed result."""
        result = ProcessingResult(
            success=False,
            message_id="msg-456",
            error_message="Test error"
        )

        repr_str = repr(result)
        assert "success=False" in repr_str
        assert "msg-456" in repr_str
        assert "Test error" in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
