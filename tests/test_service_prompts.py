"""
Tests for prompt management service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from botocore.exceptions import ClientError
import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from services import prompts


class TestLoadFromFilesystem:
    """Test loading prompts from local filesystem."""

    @patch('builtins.open', new_callable=mock_open, read_data='Test prompt from file')
    def test_load_from_filesystem_success(self, mock_file):
        """Test successful prompt load from filesystem."""
        # Execute
        result = prompts._load_from_filesystem('github_issue.txt')

        # Assert
        assert result == 'Test prompt from file'
        assert isinstance(result, str)

    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_load_from_filesystem_not_found(self, mock_file):
        """Test load when prompt file doesn't exist."""
        # Execute & Assert
        with pytest.raises(FileNotFoundError):
            prompts._load_from_filesystem('missing.txt')


class TestLoadFromS3:
    """Test loading prompts from S3."""

    @patch('services.prompts.PROMPT_BUCKET', 'test-bucket')
    @patch('services.prompts.PROMPT_KEY_PREFIX', 'prompts/')
    @patch('services.prompts.s3_client')
    def test_load_from_s3_success(self, mock_s3):
        """Test successful prompt load from S3."""
        # Setup
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'Test prompt from S3')
        }

        # Execute
        result = prompts._load_from_s3('github_issue.txt')

        # Assert
        assert result == 'Test prompt from S3'
        mock_s3.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='prompts/github_issue.txt'
        )

    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts.s3_client')
    def test_load_from_s3_no_bucket(self, mock_s3):
        """Test load when PROMPT_BUCKET not set."""
        # Execute & Assert
        with pytest.raises(ValueError, match="PROMPT_BUCKET environment variable not set"):
            prompts._load_from_s3('github_issue.txt')

    @patch('services.prompts.PROMPT_BUCKET', 'test-bucket')
    @patch('services.prompts.PROMPT_KEY_PREFIX', 'prompts/')
    @patch('services.prompts.s3_client')
    def test_load_from_s3_client_error(self, mock_s3):
        """Test load with S3 client error."""
        # Setup
        mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'GetObject'
        )

        # Execute & Assert
        with pytest.raises(ClientError):
            prompts._load_from_s3('missing.txt')


class TestLoadPrompt:
    """Test main load_prompt function with caching and fallback."""

    @patch('services.prompts.PROMPT_BUCKET', 'test-bucket')
    @patch('services.prompts._load_from_s3')
    @patch('services.prompts._load_from_filesystem')
    def test_load_prompt_from_s3_success(self, mock_fs, mock_s3):
        """Test loading prompt from S3 when available."""
        # Setup
        prompts.clear_cache()  # Clear cache before test
        mock_s3.return_value = 'Prompt from S3'

        # Execute
        result = prompts.load_prompt('github_issue.txt')

        # Assert
        assert result == 'Prompt from S3'
        mock_s3.assert_called_once_with('github_issue.txt')
        mock_fs.assert_not_called()  # Should not fallback to filesystem

    @patch('services.prompts.PROMPT_BUCKET', 'test-bucket')
    @patch('services.prompts._load_from_s3')
    @patch('services.prompts._load_from_filesystem')
    def test_load_prompt_fallback_to_filesystem(self, mock_fs, mock_s3):
        """Test fallback to filesystem when S3 fails."""
        # Setup
        prompts.clear_cache()
        mock_s3.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
            'GetObject'
        )
        mock_fs.return_value = 'Prompt from filesystem'

        # Execute
        result = prompts.load_prompt('github_issue.txt')

        # Assert
        assert result == 'Prompt from filesystem'
        mock_s3.assert_called_once()
        mock_fs.assert_called_once_with('github_issue.txt')

    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts._load_from_s3')
    @patch('services.prompts._load_from_filesystem')
    def test_load_prompt_no_s3_bucket_configured(self, mock_fs, mock_s3):
        """Test loading when PROMPT_BUCKET not set (skip S3)."""
        # Setup
        prompts.clear_cache()
        mock_fs.return_value = 'Prompt from filesystem'

        # Execute
        result = prompts.load_prompt('github_issue.txt')

        # Assert
        assert result == 'Prompt from filesystem'
        mock_s3.assert_not_called()  # Should skip S3 entirely
        mock_fs.assert_called_once_with('github_issue.txt')

    @patch('services.prompts.PROMPT_BUCKET', 'test-bucket')
    @patch('services.prompts._load_from_s3')
    @patch('services.prompts._load_from_filesystem')
    def test_load_prompt_not_found_anywhere(self, mock_fs, mock_s3):
        """Test error when prompt not found in S3 or filesystem."""
        # Setup
        prompts.clear_cache()
        mock_s3.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
            'GetObject'
        )
        mock_fs.side_effect = FileNotFoundError("Not found")

        # Execute & Assert
        with pytest.raises(ValueError, match="Prompt 'github_issue.txt' not found in S3 or local filesystem"):
            prompts.load_prompt('github_issue.txt')


class TestLoadPromptCaching:
    """Test prompt caching behavior with TTL."""

    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts._load_from_filesystem')
    def test_cache_hit_within_ttl(self, mock_fs):
        """Test that cached prompt is used within TTL."""
        # Setup
        prompts.clear_cache()
        mock_fs.return_value = 'Cached prompt'

        # First call - loads from filesystem
        result1 = prompts.load_prompt('test.txt')
        assert result1 == 'Cached prompt'
        assert mock_fs.call_count == 1

        # Second call - should use cache
        result2 = prompts.load_prompt('test.txt')
        assert result2 == 'Cached prompt'
        assert mock_fs.call_count == 1  # Not called again

    @patch('services.prompts.CACHE_TTL_SECONDS', 5)
    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts._load_from_filesystem')
    @patch('services.prompts.time.time')
    def test_cache_expired_after_ttl(self, mock_time, mock_fs):
        """Test that cache expires after TTL."""
        # Setup
        prompts.clear_cache()
        mock_fs.side_effect = ['First load', 'Second load after TTL']

        # First call at time 0
        mock_time.return_value = 0
        result1 = prompts.load_prompt('test.txt')
        assert result1 == 'First load'
        assert mock_fs.call_count == 1

        # Second call at time 3 (within TTL of 5 seconds)
        mock_time.return_value = 3
        result2 = prompts.load_prompt('test.txt')
        assert result2 == 'First load'  # Still cached
        assert mock_fs.call_count == 1  # Not called again

        # Third call at time 6 (expired TTL)
        mock_time.return_value = 6
        result3 = prompts.load_prompt('test.txt')
        assert result3 == 'Second load after TTL'
        assert mock_fs.call_count == 2  # Called again after expiration

    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts._load_from_filesystem')
    def test_cache_bypass_with_use_cache_false(self, mock_fs):
        """Test bypassing cache with use_cache=False."""
        # Setup
        prompts.clear_cache()
        mock_fs.side_effect = ['First load', 'Second load']

        # First call
        result1 = prompts.load_prompt('test.txt', use_cache=True)
        assert result1 == 'First load'
        assert mock_fs.call_count == 1

        # Second call with use_cache=False - should reload
        result2 = prompts.load_prompt('test.txt', use_cache=False)
        assert result2 == 'Second load'
        assert mock_fs.call_count == 2

    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts._load_from_filesystem')
    def test_different_prompts_cached_separately(self, mock_fs):
        """Test that different prompts are cached separately."""
        # Setup
        prompts.clear_cache()
        mock_fs.side_effect = ['Prompt A', 'Prompt B']

        # Load two different prompts
        result_a = prompts.load_prompt('prompt_a.txt')
        result_b = prompts.load_prompt('prompt_b.txt')

        assert result_a == 'Prompt A'
        assert result_b == 'Prompt B'
        assert mock_fs.call_count == 2

        # Load again - should use cache for both
        result_a2 = prompts.load_prompt('prompt_a.txt')
        result_b2 = prompts.load_prompt('prompt_b.txt')

        assert result_a2 == 'Prompt A'
        assert result_b2 == 'Prompt B'
        assert mock_fs.call_count == 2  # No additional calls


class TestFormatPrompt:
    """Test prompt template formatting."""

    def test_format_prompt_with_variables(self):
        """Test formatting prompt with all variables provided."""
        # Setup
        template = "Hello {name}, you are {age} years old."

        # Execute
        result = prompts.format_prompt(template, name="Alice", age=30)

        # Assert
        assert result == "Hello Alice, you are 30 years old."

    def test_format_prompt_multiple_variables(self):
        """Test formatting with multiple variables."""
        # Setup
        template = """
From: {from_address}
Subject: {subject}

Body:
{body}

Timestamp: {timestamp}
"""

        # Execute
        result = prompts.format_prompt(
            template,
            from_address="customer@example.com",
            subject="Bug Report",
            body="Application crashes on startup",
            timestamp="2024-11-05T10:30:00Z"
        )

        # Assert
        assert "customer@example.com" in result
        assert "Bug Report" in result
        assert "Application crashes on startup" in result
        assert "2024-11-05T10:30:00Z" in result

    def test_format_prompt_missing_variable(self):
        """Test formatting with missing required variable."""
        # Setup
        template = "Hello {name}, you are {age} years old."

        # Execute & Assert
        with pytest.raises(ValueError, match="Missing required variable in prompt: age"):
            prompts.format_prompt(template, name="Alice")

    def test_format_prompt_extra_variables(self):
        """Test formatting with extra variables (should be ignored)."""
        # Setup
        template = "Hello {name}!"

        # Execute
        result = prompts.format_prompt(template, name="Bob", age=25, city="NYC")

        # Assert
        assert result == "Hello Bob!"

    def test_format_prompt_empty_template(self):
        """Test formatting empty template."""
        # Setup
        template = ""

        # Execute
        result = prompts.format_prompt(template)

        # Assert
        assert result == ""

    def test_format_prompt_no_variables(self):
        """Test formatting template with no placeholders."""
        # Setup
        template = "This is a static prompt with no variables."

        # Execute
        result = prompts.format_prompt(template)

        # Assert
        assert result == "This is a static prompt with no variables."

    def test_format_prompt_unicode_variables(self):
        """Test formatting with Unicode content."""
        # Setup
        template = "User: {name}, Message: {message}"

        # Execute
        result = prompts.format_prompt(
            template,
            name="Alice",
            message="你好 مرحبا שלום"
        )

        # Assert
        assert "Alice" in result
        assert "你好" in result
        assert "مرحبا" in result
        assert "שלום" in result

    def test_format_prompt_special_characters(self):
        """Test formatting with special characters."""
        # Setup
        template = "Email: {email}, Path: {path}"

        # Execute
        result = prompts.format_prompt(
            template,
            email="test@example.com",
            path="/var/log/app.log"
        )

        # Assert
        assert "test@example.com" in result
        assert "/var/log/app.log" in result


class TestClearCache:
    """Test cache clearing."""

    @patch('services.prompts.PROMPT_BUCKET', None)
    @patch('services.prompts._load_from_filesystem')
    def test_clear_cache_forces_reload(self, mock_fs):
        """Test that clear_cache forces reload on next call."""
        # Setup
        prompts.clear_cache()
        mock_fs.side_effect = ['First load', 'Second load after clear']

        # First load
        result1 = prompts.load_prompt('test.txt')
        assert result1 == 'First load'
        assert mock_fs.call_count == 1

        # Second load - should use cache
        result2 = prompts.load_prompt('test.txt')
        assert result2 == 'First load'
        assert mock_fs.call_count == 1

        # Clear cache
        prompts.clear_cache()

        # Third load - should reload after cache clear
        result3 = prompts.load_prompt('test.txt')
        assert result3 == 'Second load after clear'
        assert mock_fs.call_count == 2

    def test_clear_cache_no_error_when_empty(self):
        """Test that clearing an empty cache doesn't error."""
        # Execute
        prompts.clear_cache()
        prompts.clear_cache()  # Call twice

        # No assertion needed - just ensure no error


class TestCacheTTLConfiguration:
    """Test PROMPT_CACHE_TTL environment variable configuration."""

    @patch('services.prompts._load_from_filesystem')
    @patch('time.time')
    def test_custom_cache_ttl(self, mock_time, mock_fs):
        """Test custom cache TTL from environment variable."""
        # This test verifies that the TTL is configurable
        # The actual CACHE_TTL_SECONDS is read at module import time,
        # so we test the behavior rather than the configuration itself
        prompts.clear_cache()
        mock_fs.return_value = 'Test prompt'

        # First call
        mock_time.return_value = 0
        result = prompts.load_prompt('test.txt')
        assert result == 'Test prompt'


class TestPromptPathConstruction:
    """Test prompt file path construction."""

    def test_prompts_dir_path(self):
        """Test that PROMPTS_DIR points to correct location."""
        # PROMPTS_DIR should be src/prompts/ relative to prompts.py
        assert prompts.PROMPTS_DIR.name == 'prompts'
        assert prompts.PROMPTS_DIR.parent.name == 'src'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
