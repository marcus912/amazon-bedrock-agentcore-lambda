# amazon-bedrock-agentcore-lambda Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-12

## Active Technologies

- Python 3.13 (AWS Lambda runtime) + boto3>=1.34.0 (Bedrock Agent Runtime support), botocore>=1.34.0
- Three-layer architecture: handlers → services → integrations
- AWS SAM for deployment and infrastructure
- uv for package management

## Project Structure

```text
src/
├── integrations/              # Layer 3: AWS service integrations
│   └── agentcore_invocation.py
├── services/                  # Layer 2: Utility functions
│   ├── email.py
│   └── s3.py
├── sqs_email_handler.py       # Layer 1: Lambda handlers
└── requirements.txt
tests/
├── integrations/
├── services/
└── events/
```

## Architecture Principles

**Three-Layer Pattern**:
1. **Handlers** (Layer 1): Business logic, Lambda entry points
2. **Services** (Layer 2): Reusable utilities (email, S3)
3. **Integrations** (Layer 3): AWS service wrappers (Bedrock)

**Key Decisions**:
- Module-level initialization for boto3 clients (thread-safe, reused)
- Environment variables read at import time
- Custom exceptions for error handling
- Structured logging throughout
- Exponential backoff for transient failures

## Commands

**Development**:
```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

**Deployment**:
```bash
# Deploy to dev (default)
bin/deploy.sh

# Deploy to specific environment
ENVIRONMENT=staging bin/deploy.sh
ENVIRONMENT=prod bin/deploy.sh
```

## Code Style

Python 3.13: Follow PEP 8 and type hints where beneficial

## Features

### ✅ 001-shared-agent-invocation (Completed)

**Purpose**: Shared Python module for invoking Bedrock AgentCore agents from Lambda handlers

**Components**:
- `src/integrations/agentcore_invocation.py`: Core agent invocation module
  - Uses `boto3.client('bedrock-agentcore')` with `invoke_agent_runtime()` method
  - `invoke_agent(prompt, session_id=None)`: Main API
  - Custom exceptions: ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException
  - Automatic session ID generation (33+ chars, UUID4)
  - Retry logic with exponential backoff (3 attempts)
  - JSON response parsing with graceful fallback
- `src/services/email.py`: Email parsing utilities
  - `extract_email_body(email_content)`: Extract plain text from emails
  - `parse_email_headers(email_content)`: Parse email headers
- `src/services/s3.py`: S3 operations
  - `fetch_email_from_s3(bucket, key)`: Fetch email from S3
  - `upload_processed_result(bucket, key, content)`: Upload results

**Configuration**:
- Environment variable: `AGENT_RUNTIME_ARN` (required)
- Multi-environment support: dev, staging, prod
- SAM template parameter: `AgentRuntimeArn`

**Usage Example**:
```python
from integrations import agentcore_invocation
from services import email, s3

# Fetch and parse email
email_content = s3.fetch_email_from_s3(bucket, key)
body = email.extract_email_body(email_content)

# Invoke agent
summary = agentcore_invocation.invoke_agent(
    prompt=f"Summarize: {body}",
    session_id=None
)
```

## Recent Changes

- 2025-11-12: Completed 001-shared-agent-invocation feature
  - Implemented three-layer architecture
  - Added Bedrock Agent invocation module with retry logic
  - Created email and S3 service utilities
  - Refactored SQS email handler to use new architecture
  - Updated SAM template for multi-environment configuration

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
