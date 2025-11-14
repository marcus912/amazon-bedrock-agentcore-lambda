"""
Pytest configuration and fixtures for all tests.
"""

import os
import sys
import pytest

# Add src to Python path before any imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

# Set up test environment variables before importing any modules
os.environ.setdefault('AGENT_RUNTIME_ARN', 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test-agent-ABC123')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('LOG_LEVEL', 'INFO')


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables for all tests."""
    # Environment variables are already set above
    yield
    # Cleanup after all tests (optional)
