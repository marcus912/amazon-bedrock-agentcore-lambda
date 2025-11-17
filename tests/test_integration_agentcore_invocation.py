"""
Tests for Bedrock AgentCore invocation integration.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))


class TestModuleInitialization:
    """Test module-level initialization and configuration."""

    @pytest.mark.skip(reason="Module is already loaded by conftest.py, cannot test initialization errors")
    def test_missing_agent_runtime_arn(self):
        """Test that ConfigurationError is raised when AGENT_RUNTIME_ARN is missing."""
        pass

    @pytest.mark.skip(reason="Module is already loaded by conftest.py, cannot test initialization errors")
    def test_invalid_agent_runtime_arn_format(self):
        """Test that ConfigurationError is raised for invalid ARN format."""
        pass


class TestInvokeAgent:
    """Test the invoke_agent function."""

    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_invoke_agent_success(self, mock_bedrock_client):
        """Test successful agent invocation."""
        # Setup
        from integrations import agentcore_invocation

        mock_response = {
            'response': MagicMock(
                read=lambda: json.dumps({'output': 'This is the agent response'}).encode('utf-8')
            )
        }
        mock_bedrock_client.invoke_agent_runtime.return_value = mock_response

        # Execute
        result = agentcore_invocation.invoke_agent(
            prompt="What is the weather today?"
        )

        # Assert
        assert result == 'This is the agent response'
        mock_bedrock_client.invoke_agent_runtime.assert_called_once()
        call_args = mock_bedrock_client.invoke_agent_runtime.call_args
        assert 'agentRuntimeArn' in call_args[1]
        assert 'runtimeSessionId' in call_args[1]
        assert 'payload' in call_args[1]

    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_invoke_agent_with_session_id(self, mock_bedrock_client):
        """Test agent invocation with custom session ID."""
        from integrations import agentcore_invocation

        mock_response = {
            'response': MagicMock(
                read=lambda: json.dumps({'output': 'Response'}).encode('utf-8')
            )
        }
        mock_bedrock_client.invoke_agent_runtime.return_value = mock_response

        # Execute with custom session ID
        custom_session = "session-" + "a" * 30  # 38 chars total (meets 33+ requirement)
        result = agentcore_invocation.invoke_agent(
            prompt="Follow up question",
            session_id=custom_session
        )

        # Assert
        assert result == 'Response'
        call_args = mock_bedrock_client.invoke_agent_runtime.call_args
        assert call_args[1]['runtimeSessionId'] == custom_session

    def test_invoke_agent_empty_prompt(self):
        """Test that ValidationException is raised for empty prompt."""
        from integrations import agentcore_invocation

        with pytest.raises(agentcore_invocation.ValidationException, match="non-empty string"):
            agentcore_invocation.invoke_agent(prompt="")

    def test_invoke_agent_none_prompt(self):
        """Test that ValidationException is raised for None prompt."""
        from integrations import agentcore_invocation

        with pytest.raises(agentcore_invocation.ValidationException, match="non-empty string"):
            agentcore_invocation.invoke_agent(prompt=None)

    def test_invoke_agent_short_session_id(self):
        """Test that ValidationException is raised for short session ID."""
        from integrations import agentcore_invocation

        with pytest.raises(agentcore_invocation.ValidationException, match="at least 33 characters"):
            agentcore_invocation.invoke_agent(
                prompt="Test",
                session_id="short"  # Too short
            )

    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_invoke_agent_resource_not_found(self, mock_bedrock_client):
        """Test AgentNotFoundException when agent doesn't exist."""
        from integrations import agentcore_invocation

        # Setup
        mock_bedrock_client.invoke_agent_runtime.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Agent not found'
                }
            },
            'InvokeAgentRuntime'
        )

        # Execute & Assert
        with pytest.raises(agentcore_invocation.AgentNotFoundException, match="Agent not found"):
            agentcore_invocation.invoke_agent(prompt="Test prompt")

    @patch('integrations.agentcore_invocation.bedrock_client')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_invoke_agent_throttling_with_retry(self, mock_sleep, mock_bedrock_client):
        """Test retry logic for throttling errors."""
        from integrations import agentcore_invocation

        # Setup - Fail twice, succeed on third attempt
        mock_bedrock_client.invoke_agent_runtime.side_effect = [
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
                'InvokeAgentRuntime'
            ),
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
                'InvokeAgentRuntime'
            ),
            {
                'response': MagicMock(
                    read=lambda: json.dumps({'output': 'Success after retry'}).encode('utf-8')
                )
            }
        ]

        # Execute
        result = agentcore_invocation.invoke_agent(prompt="Test prompt")

        # Assert
        assert result == 'Success after retry'
        assert mock_bedrock_client.invoke_agent_runtime.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch('integrations.agentcore_invocation.bedrock_client')
    @patch('time.sleep')
    def test_invoke_agent_throttling_max_retries_exceeded(self, mock_sleep, mock_bedrock_client):
        """Test ThrottlingException when max retries exceeded."""
        from integrations import agentcore_invocation

        # Setup - Always fail
        mock_bedrock_client.invoke_agent_runtime.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
            'InvokeAgentRuntime'
        )

        # Execute & Assert
        with pytest.raises(agentcore_invocation.ThrottlingException, match="after 3 attempts"):
            agentcore_invocation.invoke_agent(prompt="Test prompt")

        assert mock_bedrock_client.invoke_agent_runtime.call_count == 3

    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_invoke_agent_generic_client_error(self, mock_bedrock_client):
        """Test that generic ClientError is propagated."""
        from integrations import agentcore_invocation

        # Setup
        mock_bedrock_client.invoke_agent_runtime.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}},
            'InvokeAgentRuntime'
        )

        # Execute & Assert
        with pytest.raises(ClientError):
            agentcore_invocation.invoke_agent(prompt="Test prompt")

    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_invoke_agent_empty_response(self, mock_bedrock_client):
        """Test handling of empty agent response."""
        from integrations import agentcore_invocation

        # Setup
        mock_response = {
            'response': MagicMock(read=lambda: b'')
        }
        mock_bedrock_client.invoke_agent_runtime.return_value = mock_response

        # Execute
        result = agentcore_invocation.invoke_agent(prompt="Test prompt")

        # Assert
        assert result == ''

    @patch('integrations.agentcore_invocation.bedrock_client')
    def test_invoke_agent_malformed_json_response(self, mock_bedrock_client):
        """Test handling of malformed JSON in response."""
        from integrations import agentcore_invocation

        # Setup
        mock_response = {
            'response': MagicMock(read=lambda: b'Not valid JSON')
        }
        mock_bedrock_client.invoke_agent_runtime.return_value = mock_response

        # Execute
        result = agentcore_invocation.invoke_agent(prompt="Test prompt")

        # Assert - Should fallback to raw bytes
        assert result == 'Not valid JSON'


class TestGenerateSessionId:
    """Test session ID generation."""

    def test_generate_session_id_format(self):
        """Test that generated session ID has correct format."""
        from integrations import agentcore_invocation

        session_id = agentcore_invocation._generate_session_id()

        # Assert
        assert session_id.startswith('session-')
        assert len(session_id) >= 33
        assert '-' in session_id[8:]  # UUID should have hyphens

    def test_generate_session_id_unique(self):
        """Test that generated session IDs are unique."""
        from integrations import agentcore_invocation

        session_id1 = agentcore_invocation._generate_session_id()
        session_id2 = agentcore_invocation._generate_session_id()

        assert session_id1 != session_id2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
