"""
Amazon Bedrock AgentCore Invocation Module

This module provides a simple interface for invoking Bedrock AgentCore agents
from Lambda handlers. It handles configuration, retry logic, error mapping,
and response parsing.

Usage:
    from integrations import agentcore_invocation

    response = agentcore_invocation.invoke_agent(
        prompt="What is the weather today?",
        session_id=None  # Optional, will be auto-generated if None
    )
    print(response)  # Agent's response as a string
"""

import json
import logging
import os
import time
import uuid
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exception Classes
# ============================================================================

class ConfigurationError(Exception):
    """Raised when module configuration is invalid or missing."""
    pass


class AgentNotFoundException(Exception):
    """Raised when the specified Bedrock agent cannot be found."""
    pass


class ThrottlingException(Exception):
    """Raised when Bedrock API requests are throttled."""
    pass


class ValidationException(Exception):
    """Raised when input validation fails."""
    pass


# ============================================================================
# Module-Level Configuration and Initialization
# ============================================================================

def _read_agent_runtime_arn() -> str:
    """
    Read and validate AGENT_RUNTIME_ARN from environment variables.

    Returns:
        str: The validated agent runtime ARN

    Raises:
        ConfigurationError: If AGENT_RUNTIME_ARN is missing or invalid
    """
    agent_runtime_arn = os.environ.get('AGENT_RUNTIME_ARN')

    if not agent_runtime_arn:
        raise ConfigurationError(
            "AGENT_RUNTIME_ARN environment variable is required but not set. "
            "Please configure this in your SAM template or Lambda environment."
        )

    # Validate ARN format (basic check)
    if not agent_runtime_arn.startswith('arn:aws:bedrock-agentcore:'):
        raise ConfigurationError(
            f"AGENT_RUNTIME_ARN has invalid format. "
            f"Expected ARN starting with 'arn:aws:bedrock-agentcore:', "
            f"got: '{agent_runtime_arn[:50]}...'"
        )

    logger.info(f"Agent Runtime ARN configured: {agent_runtime_arn}")
    return agent_runtime_arn


def _initialize_bedrock_client():
    """
    Initialize boto3 Bedrock Agent Runtime client with retry configuration.

    Returns:
        boto3.client: Configured Bedrock Agent Runtime client
    """
    # Configure retry strategy for transient failures
    retry_config = Config(
        retries={
            'max_attempts': 3,
            'mode': 'adaptive'  # Adaptive retry mode for intelligent throttling
        }
    )

    client = boto3.client(
        'bedrock-agent-runtime',
        config=retry_config
    )

    logger.info("Bedrock Agent Runtime client initialized successfully")
    return client


# Initialize at module import time (thread-safe, reused across invocations)
try:
    AGENT_RUNTIME_ARN = _read_agent_runtime_arn()
    bedrock_client = _initialize_bedrock_client()
except ConfigurationError as e:
    logger.error(f"Module initialization failed: {e}")
    raise


# ============================================================================
# Core Agent Invocation Functions
# ============================================================================

def _generate_session_id() -> str:
    """
    Generate a session ID for agent invocation.

    Bedrock requires session IDs to be at least 33 characters long.

    Returns:
        str: A valid session ID (33+ characters)
    """
    # Generate UUID4 and prefix with "session-" to ensure 33+ characters
    session_id = f"session-{uuid.uuid4()}"
    return session_id


def invoke_agent(prompt: str, session_id: Optional[str] = None, **kwargs) -> str:
    """
    Invoke a Bedrock AgentCore agent with the given prompt.

    This function provides a simple interface for Lambda handlers to invoke
    Bedrock agents. It handles session management, payload formatting, and
    response parsing automatically.

    Args:
        prompt: The input text to send to the agent (required, non-empty string)
        session_id: Optional session ID for multi-turn conversations.
                   If None, a new session ID will be generated automatically.
        **kwargs: Additional parameters (reserved for future use)

    Returns:
        str: The agent's complete response text

    Raises:
        ValidationException: If prompt is invalid (empty or wrong type)
        AgentNotFoundException: If the configured agent cannot be found
        ThrottlingException: If requests are being throttled after retries
        ConfigurationError: If module configuration is invalid
        ClientError: For other AWS service errors

    Example:
        >>> from integrations import agentcore_invocation
        >>> response = agentcore_invocation.invoke_agent(
        ...     prompt="What is the weather in San Francisco?",
        ...     session_id=None
        ... )
        >>> print(response)
        "The current weather in San Francisco is 68°F with partly cloudy skies."

        # Multi-turn conversation
        >>> session = None
        >>> response1 = agentcore_invocation.invoke_agent(
        ...     prompt="Tell me about Python.",
        ...     session_id=session
        ... )
        >>> # Extract session from first response metadata (if needed)
        >>> response2 = agentcore_invocation.invoke_agent(
        ...     prompt="Can you give me an example?",
        ...     session_id=session  # Same session for context
        ... )
    """
    start_time = time.time()

    # Validate prompt
    if not prompt or not isinstance(prompt, str):
        raise ValidationException(
            f"Prompt must be a non-empty string. Got: {type(prompt).__name__} "
            f"with value: {repr(prompt[:50]) if prompt else 'None'}"
        )

    # Validate session_id if provided
    if session_id is not None:
        if not isinstance(session_id, str):
            raise ValidationException(
                f"session_id must be a string or None. Got: {type(session_id).__name__}"
            )
        # Basic UUID4 format validation (optional but helps catch obvious errors)
        if len(session_id) < 33:
            raise ValidationException(
                f"session_id must be at least 33 characters long (Bedrock requirement). "
                f"Got: {len(session_id)} characters"
            )

    # Generate session ID if not provided
    if session_id is None:
        session_id = _generate_session_id()
        logger.info(f"Generated new session ID: {session_id}")
    else:
        logger.info(f"Using provided session ID: {session_id}")

    # Format payload as JSON string (Bedrock requirement)
    payload = json.dumps({"prompt": prompt})

    logger.info(
        f"Invoking agent: prompt_length={len(prompt)}, "
        f"session_id_length={len(session_id)}, "
        f"agent_arn={AGENT_RUNTIME_ARN[:50]}..."
    )

    # Retry logic for transient errors
    max_retries = 3
    retryable_errors = ['ThrottlingException', 'InternalServerException', 'ServiceQuotaExceededException']

    for attempt in range(max_retries):
        try:
            # Call Bedrock Agent Runtime API
            response = bedrock_client.invoke_agent(
                agentId=AGENT_RUNTIME_ARN,
                agentAliasId='TSTALIASID',  # Use test alias or extract from ARN
                sessionId=session_id,
                inputText=prompt
            )

            # Parse EventStream response
            agent_output = _parse_eventstream_response(response)

            execution_time = time.time() - start_time
            logger.info(
                f"Agent invocation succeeded: "
                f"response_length={len(agent_output)}, "
                f"execution_time={execution_time:.2f}s, "
                f"attempts={attempt + 1}"
            )

            return agent_output

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))

            # Map AWS errors to domain-specific exceptions
            if error_code == 'ResourceNotFoundException':
                logger.error(
                    f"Agent not found: agent_arn={AGENT_RUNTIME_ARN}, "
                    f"error={error_message}"
                )
                raise AgentNotFoundException(
                    f"Agent not found: {AGENT_RUNTIME_ARN}. "
                    f"Verify the agent exists and is active. Error: {error_message}"
                )
            elif error_code in retryable_errors:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt * 100ms
                    wait_time = (2 ** attempt) * 0.1
                    logger.warning(
                        f"Retryable error encountered: error_code={error_code}, "
                        f"attempt={attempt + 1}/{max_retries}, "
                        f"retry_after={wait_time:.2f}s, "
                        f"agent_arn={AGENT_RUNTIME_ARN[:50]}..."
                    )
                    time.sleep(wait_time)
                    continue  # Retry
                else:
                    # Last attempt failed
                    logger.error(
                        f"Max retries exceeded: error_code={error_code}, "
                        f"attempts={max_retries}, "
                        f"agent_arn={AGENT_RUNTIME_ARN[:50]}..."
                    )
                    raise ThrottlingException(
                        f"Request throttled by Bedrock service after {max_retries} attempts. "
                        f"Retry after a longer delay. Error: {error_message}"
                    )
            else:
                logger.error(
                    f"Agent invocation failed: error_code={error_code}, "
                    f"error_message={error_message}, "
                    f"agent_arn={AGENT_RUNTIME_ARN[:50]}..."
                )
                raise


def _parse_eventstream_response(response: dict) -> str:
    """
    Parse the EventStream response from Bedrock Agent Runtime.

    Bedrock returns responses as an EventStream with multiple chunks.
    This function reads and aggregates all chunks into a complete response.

    Args:
        response: The response dict from invoke_agent() API call

    Returns:
        str: The complete agent output as a string

    Raises:
        Exception: If response parsing fails
    """
    output_text = ""

    # Check if response contains the expected structure
    if 'response' not in response:
        logger.error(f"Unexpected response structure: {response.keys()}")
        raise Exception("Invalid response structure from Bedrock Agent Runtime")

    # Read the streaming response body
    event_stream = response['response']

    try:
        # Call .read() to get the response content
        response_bytes = event_stream.read()

        # Parse JSON response
        if response_bytes:
            try:
                response_data = json.loads(response_bytes.decode('utf-8'))
                output_text = response_data.get('output', '')
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                # If JSON parsing fails, use raw bytes as fallback
                output_text = response_bytes.decode('utf-8', errors='ignore')
        else:
            logger.warning("Received empty response from agent")
            output_text = ""

    except Exception as e:
        logger.error(f"Error reading EventStream: {e}")
        raise

    return output_text
