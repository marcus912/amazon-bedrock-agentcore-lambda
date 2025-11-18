"""
Amazon Bedrock AgentCore Invocation Module

This module provides a simple interface for invoking Bedrock AgentCore agents
from Lambda handlers using the bedrock-agentcore client API.

Usage:
    from integrations import agentcore_invocation

    response = agentcore_invocation.invoke_agent(
        prompt="What is the weather today?",
        session_id=None  # Optional, will be auto-generated (33+ chars)
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
    if not agent_runtime_arn.startswith('arn:aws:bedrock'):
        raise ConfigurationError(
            f"AGENT_RUNTIME_ARN has invalid format. "
            f"Expected ARN starting with 'arn:aws:bedrock', "
            f"got: '{agent_runtime_arn[:50]}...'"
        )

    logger.info(f"Agent Runtime ARN configured: {agent_runtime_arn}")
    return agent_runtime_arn


def _initialize_bedrock_client():
    """
    Initialize boto3 Bedrock AgentCore client with timeout configuration.

    Returns:
        boto3.client: Configured Bedrock AgentCore client
    """
    # Configure with NO retries and strict timeouts to prevent infinite loops
    # Lambda timeout will handle failure scenarios
    client_config = Config(
        retries={
            'max_attempts': 0,  # 0 attempts = 1 total call, NO retries
            'mode': 'standard'
        },
        connect_timeout=10,  # 10 seconds to establish connection
        read_timeout=120     # 120 seconds max for reading response (prevents infinite hang)
    )

    # Get region from environment or use default
    region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-west-2'))

    # Create Bedrock AgentCore client
    client = boto3.client(
        'bedrock-agentcore',
        region_name=region,
        config=client_config
    )

    logger.info(
        f"Bedrock AgentCore client initialized: region={region}, "
        f"connect_timeout=10s, read_timeout=120s, max_attempts=0 (no retries)"
    )
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


def invoke_agent(prompt: str, session_id: Optional[str] = None) -> str:
    """
    Invoke a Bedrock AgentCore agent with the given prompt.

    This function provides a simple interface for Lambda handlers to invoke
    Bedrock agents. It handles session management, payload formatting, and
    response parsing automatically.

    Args:
        prompt: The input text to send to the agent (required, non-empty string)
        session_id: Optional session ID for multi-turn conversations.
                   If None, a new session ID will be generated automatically.

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

    # Format payload as JSON string (AgentCore API requirement)
    payload = json.dumps({"prompt": prompt})

    logger.info(
        f"Invoking agent: prompt_length={len(prompt)}, "
        f"session_id_length={len(session_id)}, "
        f"agent_arn={AGENT_RUNTIME_ARN[:50]}..."
    )

    try:
        # Call Bedrock AgentCore API (NO RETRIES - fail fast)
        response = bedrock_client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,  # Use full ARN
            runtimeSessionId=session_id,
            payload=payload,
            qualifier="DEFAULT"  # Optional qualifier
        )

        # Parse AgentCore response
        # WARNING: This read() can potentially hang if response stream doesn't complete
        # The boto3 client timeout should prevent infinite hangs
        response_body = response['response'].read()

        # Handle empty response
        if not response_body:
            logger.warning("Agent returned empty response")
            return ""

        # Parse JSON response
        try:
            response_data = json.loads(response_body)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse JSON response: {json_err}, body: {response_body[:200]}")
            # Return raw response if JSON parsing fails
            return response_body.decode('utf-8') if isinstance(response_body, bytes) else str(response_body)

        # Extract the agent output from response
        agent_output = response_data.get('response', response_data.get('output', str(response_data)))

        execution_time = time.time() - start_time
        logger.info(
            f"Agent invocation succeeded: "
            f"response_length={len(agent_output)}, "
            f"execution_time={execution_time:.2f}s"
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
        elif error_code == 'ThrottlingException':
            logger.error(f"Request throttled: {error_message}")
            raise ThrottlingException(f"Request throttled by Bedrock service: {error_message}")
        else:
            logger.error(
                f"Agent invocation failed: error_code={error_code}, "
                f"error_message={error_message}, "
                f"agent_arn={AGENT_RUNTIME_ARN[:50]}..."
            )
            raise
