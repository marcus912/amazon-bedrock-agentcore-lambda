"""
Prompt management utilities.

This module loads AI agent prompts with the following priority:
1. Local filesystem (prompts/ directory packaged with Lambda)
2. S3 override (optional, for runtime updates without redeploy)

Prompts are cached in memory for warm Lambda invocations with TTL.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Cache TTL in seconds (default: 5 minutes)
# After this time, prompt will be reloaded from S3 on next request
CACHE_TTL_SECONDS = int(os.environ.get('PROMPT_CACHE_TTL', '300'))

# Module-level cache: {cache_key: (prompt_content, timestamp)}
_prompt_cache: Dict[str, Tuple[str, float]] = {}

# Initialize S3 client at module level (thread-safe, reused)
s3_client = boto3.client('s3')

# Configuration from environment variables
PROMPT_BUCKET = os.environ.get('PROMPT_BUCKET')
PROMPT_KEY_PREFIX = os.environ.get('PROMPT_KEY_PREFIX', 'prompts/')

# Path to prompts directory (relative to this file)
# src/services/prompts.py -> src/prompts/
# In Lambda: /var/task/prompts/
# In development: <project>/src/prompts/
PROMPTS_DIR = Path(__file__).parent.parent / 'prompts'


def _load_from_filesystem(prompt_name: str) -> str:
    """
    Load prompt from local filesystem.

    Args:
        prompt_name: Name of the prompt file

    Returns:
        str: Prompt content

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / prompt_name
    logger.info(f"Loading prompt from filesystem: {prompt_path}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    logger.info(f"Loaded prompt from filesystem: {len(content)} characters")
    return content


def _load_from_s3(prompt_name: str) -> str:
    """
    Load prompt from S3 (optional override).

    Args:
        prompt_name: Name of the prompt file

    Returns:
        str: Prompt content

    Raises:
        ValueError: If PROMPT_BUCKET not set or prompt not found
    """
    if not PROMPT_BUCKET:
        raise ValueError("PROMPT_BUCKET environment variable not set")

    s3_key = f"{PROMPT_KEY_PREFIX}{prompt_name}"
    logger.info(f"Loading prompt from S3: s3://{PROMPT_BUCKET}/{s3_key}")

    response = s3_client.get_object(
        Bucket=PROMPT_BUCKET,
        Key=s3_key
    )

    content = response['Body'].read().decode('utf-8')
    logger.info(f"Loaded prompt from S3: {len(content)} characters")
    return content


def load_prompt(prompt_name: str, use_cache: bool = True) -> str:
    """
    Load prompt template with intelligent fallback strategy and TTL-based caching.

    Loading priority:
    1. Cache (if warm Lambda invocation and not expired)
    2. S3 override (if PROMPT_BUCKET set and file exists)
    3. Local filesystem (prompts/ directory packaged with Lambda)

    Cache TTL:
    - Prompts are cached for CACHE_TTL_SECONDS (default: 5 minutes)
    - After expiration, prompt is reloaded from S3 (or filesystem if S3 unavailable)
    - This ensures S3 updates are picked up within the TTL window

    This ensures:
    - Fast loading (cache with TTL)
    - S3 updates reflected within TTL window
    - Runtime updates possible (S3 override)
    - Always works (local filesystem fallback)

    Args:
        prompt_name: Name of the prompt file (e.g., "github_issue.txt")
        use_cache: Whether to use cached version (default: True)

    Returns:
        str: The prompt template content

    Raises:
        ValueError: If prompt not found anywhere
        FileNotFoundError: If prompt missing from filesystem

    Example:
        >>> prompt = load_prompt("github_issue.txt")
        >>> len(prompt) > 0
        True
    """
    cache_key = f"prompt:{prompt_name}"
    current_time = time.time()

    # 1. Check cache first (for warm Lambda invocations)
    if use_cache and cache_key in _prompt_cache:
        cached_content, cached_time = _prompt_cache[cache_key]
        age_seconds = current_time - cached_time

        # Check if cache is still valid (within TTL)
        if age_seconds < CACHE_TTL_SECONDS:
            logger.info(
                f"Using cached prompt: {prompt_name} "
                f"(age: {int(age_seconds)}s, TTL: {CACHE_TTL_SECONDS}s)"
            )
            return cached_content
        else:
            logger.info(
                f"Cache expired for prompt: {prompt_name} "
                f"(age: {int(age_seconds)}s > TTL: {CACHE_TTL_SECONDS}s), reloading..."
            )

    prompt_content = None

    # 2. Try S3 override (if configured)
    if PROMPT_BUCKET:
        try:
            prompt_content = _load_from_s3(prompt_name)
            logger.info(f"Using S3 override for prompt: {prompt_name}")
        except (ClientError, ValueError) as e:
            logger.info(
                f"S3 override not available ({e.__class__.__name__}), "
                f"falling back to local filesystem"
            )

    # 3. Fall back to local filesystem (always available)
    if prompt_content is None:
        try:
            prompt_content = _load_from_filesystem(prompt_name)
            logger.info(f"Using local filesystem prompt: {prompt_name}")
        except FileNotFoundError:
            logger.error(
                f"Prompt not found: {prompt_name}. "
                f"Expected location: {PROMPTS_DIR / prompt_name}"
            )
            raise ValueError(
                f"Prompt '{prompt_name}' not found in S3 or local filesystem"
            )

    # Cache for future invocations with timestamp
    _prompt_cache[cache_key] = (prompt_content, current_time)

    return prompt_content


def format_prompt(template: str, **variables) -> str:
    """
    Format prompt template with variables.

    Uses Python string.format() to substitute variables in the template.

    Args:
        template: The prompt template string (with {variable} placeholders)
        **variables: Variables to substitute in the template

    Returns:
        str: Formatted prompt with all variables substituted

    Raises:
        ValueError: If a required variable is missing from the template

    Example:
        >>> template = "Hello {name}, you are {age} years old."
        >>> prompt = format_prompt(template, name="Alice", age=30)
        >>> print(prompt)
        Hello Alice, you are 30 years old.
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        missing_var = str(e).strip("'")
        logger.error(f"Missing variable in prompt template: {missing_var}")
        raise ValueError(f"Missing required variable in prompt: {missing_var}")


def clear_cache() -> None:
    """
    Clear the prompt cache.

    Useful for testing or forcing a reload from S3.

    Example:
        >>> clear_cache()
        >>> # Next load_prompt() will fetch from S3
    """
    global _prompt_cache
    _prompt_cache.clear()
    logger.info("Prompt cache cleared")
