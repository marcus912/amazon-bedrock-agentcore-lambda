# amazon-bedrock-agentcore-lambda Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-19

## Active Technologies

- Python 3.13 (AWS Lambda runtime) + boto3>=1.34.0 (Bedrock Agent Runtime support), botocore>=1.34.0
- Four-layer architecture: handler → domain → services → integrations
- Type-safe domain models using dataclasses
- AWS SAM for deployment and infrastructure
- uv for package management

## Project Structure

```text
src/
├── sqs_email_handler.py       # Thin orchestration layer (92 lines)
├── domain/                    # NEW: Business logic layer
│   ├── models.py              # Type-safe dataclasses
│   └── email_processor.py     # Email processing pipeline
├── services/                  # Utilities
│   ├── email.py
│   ├── s3.py
│   └── prompts.py
├── integrations/              # External APIs
│   └── agentcore_invocation.py
└── requirements.txt
tests/
├── test_domain_models.py
├── test_sqs_email_handler.py
├── test_integration_agentcore_invocation.py
└── test_service_*.py
```

## Architecture Principles

**Four-Layer Pattern**:
1. **Handler** (Orchestration): Thin Lambda entry point, just coordinates
2. **Domain** (Business Logic): Core email processing, type-safe models
3. **Services** (Utilities): Reusable functions (email, S3, prompts)
4. **Integrations** (External APIs): AWS service wrappers (Bedrock)

**Key Decisions**:
- Type-safe domain models with dataclasses (EmailMetadata, EmailContent, ProcessingResult)
- Module-level initialization for boto3 clients (thread-safe, reused)
- Environment variables read at import time
- Custom exceptions for error handling
- Structured logging throughout
- **Fail-fast error handling (NO retries to prevent infinite loops)**
- Strict timeouts on all boto3 clients (max_attempts=0, connect/read timeouts)
- Always consume SQS messages (return empty batchItemFailures)

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
- `src/domain/email_processor.py`: Email processing pipeline
  - `EmailProcessor.process_ses_record()`: Main business logic
  - Orchestrates: parse → fetch → process → return result
  - Returns explicit `ProcessingResult` (success/failure)
- `src/domain/models.py`: Type-safe data structures
  - `EmailMetadata`: Structured email metadata (from, subject, S3 location, etc.)
  - `EmailContent`: Parsed email content (text, HTML, attachments)
  - `ProcessingResult`: Explicit success/failure result
- `src/sqs_email_handler.py`: Lambda handler
  - Thin orchestration layer (92 lines)
  - Delegates to EmailProcessor
  - Always returns empty batchItemFailures (no retries)
- `src/integrations/agentcore_invocation.py`: Core agent invocation module
  - Uses `boto3.client('bedrock-agentcore')` with `invoke_agent_runtime()` method
  - `invoke_agent(prompt, session_id=None)`: Main API
  - Custom exceptions: ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException
  - Automatic session ID generation (33+ chars, UUID4)
  - **NO retries** (max_attempts=0, fail fast)
  - Strict timeouts (10s connect, 120s read)
  - JSON response parsing with graceful fallback
- `src/services/email.py`: Email parsing utilities
  - `extract_email_body(email_content)`: Extract plain text from emails
  - `parse_email_headers(email_content)`: Parse email headers
- `src/services/s3.py`: S3 operations
  - `fetch_email_from_s3(bucket, key)`: Fetch email from S3
  - Strict timeouts (10s connect, 60s read, no retries)
  - `upload_processed_result(bucket, key, content)`: Upload results
- `src/services/prompts.py`: Prompt management
  - Load prompts from filesystem or S3 with TTL caching
  - Strict timeouts (10s connect, 30s read, no retries)

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

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
