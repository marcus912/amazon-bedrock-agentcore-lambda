# Development Guidelines

## Stack

- Python 3.13, boto3>=1.34.0, AWS SAM, uv
- Four-layer architecture: handler → domain → services → integrations
- Type-safe dataclasses

## Architecture

**Layers**:
1. **Handler**: Thin orchestration
2. **Domain**: Business logic + type-safe models
3. **Services**: Utilities (email, S3, prompts)
4. **Integrations**: External APIs (Bedrock)

**Key patterns**:
- Type-safe models (dataclasses)
- Module-level boto3 clients (thread-safe, reused)
- Fail-fast (NO retries, strict timeouts)
- Always consume SQS messages (empty batchItemFailures)

## Commands

```bash
# Dev
uv sync                      # Install
uv run pytest               # Test
uv run ruff check .         # Lint

# Deploy
bin/deploy.sh               # Deploy to dev
ENVIRONMENT=prod bin/deploy.sh
```

## Core Components

**Agent Invocation** (`src/integrations/agentcore_invocation.py`):
- `invoke_agent()`: Synchronous invocation (waits up to 5 min, configurable)
- Auto session ID generation, strict timeouts, no retries

**Domain** (`src/domain/`):
- `EmailProcessor`: Main business logic
- Type-safe models: `EmailMetadata`, `EmailContent`, `ProcessingResult`

**Services** (`src/services/`):
- Email parsing, S3 operations, prompt management (cache → S3 → filesystem)

## Usage

```python
from integrations import agentcore_invocation

# Invoke agent (synchronous - waits up to 5 min for response)
response = agentcore_invocation.invoke_agent(
    prompt="Create GitHub issue...",
    session_id=None  # Auto-generated if not provided
)
```

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
