# Research: Shared AgentCore Invocation Lambda

**Feature**: 001-shared-agent-invocation
**Phase**: 0 (Research & Technology Decisions)
**Date**: 2025-11-11

## Overview

This document consolidates research findings for implementing a Lambda function that invokes Amazon Bedrock AgentCore agents. All technical uncertainties from the implementation plan have been resolved through AWS documentation research and best practices analysis.

## Research Areas

### 1. AWS Bedrock Agent Runtime API

**Decision**: Use `boto3` client `bedrock-agent-runtime` with `invoke_agent` operation

**Rationale**:
- Official AWS SDK for Python (boto3) provides full support for Bedrock Agent Runtime
- `invoke_agent` API accepts: `agentId`, `agentAliasId`, `sessionId`, `inputText`
- Returns streaming response with agent output, citations, and session state
- Supports session management for multi-turn conversations via `sessionId`
- Handles authentication via IAM role (no credentials in code)

**API Reference**:
```python
import boto3

client = boto3.client('bedrock-agent-runtime', region_name='us-west-2')

response = client.invoke_agent(
    agentId='AGENT_ID',
    agentAliasId='AGENT_ALIAS_ID',
    sessionId='SESSION_ID',  # Optional, auto-generated if not provided
    inputText='User input here'
)

# Response is EventStream - need to iterate chunks
for event in response['completion']:
    if 'chunk' in event:
        data = event['chunk']['bytes'].decode('utf-8')
```

**Alternatives Considered**:
- Direct HTTP API calls: Rejected due to complexity of AWS SigV4 signing
- AWS CLI wrapper: Rejected due to performance overhead and lack of type safety
- Third-party libraries: Rejected because boto3 is the official, maintained SDK

### 2. Dependency Management with uv

**Decision**: Manage boto3 via `src/requirements.txt` for Lambda runtime, use uv for dev dependencies

**Rationale**:
- Lambda deployment packages use `src/requirements.txt` (SAM convention)
- uv manages dev dependencies in `pyproject.toml` (`[project.optional-dependencies]`)
- Separation ensures Lambda package only includes runtime dependencies
- SAM build process: `sam build` installs `src/requirements.txt` into deployment package
- uv syncs dev environment: `uv sync --extra dev` for local testing

**Implementation**:
```toml
# pyproject.toml - Dev dependencies managed by uv
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-mock>=3.11.0",
    "pytest-cov>=4.1.0",
    "boto3>=1.34.0",      # For local testing
    "botocore>=1.34.0",
]
```

```txt
# src/requirements.txt - Lambda runtime dependencies
boto3>=1.34.0
botocore>=1.34.0
```

**Alternatives Considered**:
- Single dependency file: Rejected because SAM requires `src/requirements.txt`
- Lambda layers: Rejected for boto3 (already included in Lambda runtime, but need specific version for Bedrock Agent Runtime)
- Poetry: Rejected because project already uses uv

### 3. Error Handling & Retry Strategy

**Decision**: Use botocore's built-in retry config + custom exponential backoff for Bedrock-specific errors

**Rationale**:
- botocore provides automatic retries for transient AWS errors (throttling, 5xx)
- Bedrock Agent Runtime can return specific errors requiring custom handling:
  - `ResourceNotFoundException`: Agent/alias not found (don't retry)
  - `ValidationException`: Invalid input (don't retry)
  - `ThrottlingException`: Rate limit (retry with backoff)
  - `ServiceQuotaExceededException`: Quota limit (retry with backoff)
  - `InternalServerException`: AWS service error (retry)
- Custom retry uses `tenacity` library for exponential backoff

**Implementation Pattern**:
```python
from botocore.config import Config
from botocore.exceptions import ClientError
import time

# Configure boto3 client with retry
config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'  # Adaptive retry mode for throttling
    }
)

client = boto3.client('bedrock-agent-runtime', config=config)

def invoke_with_retry(agent_id, agent_alias_id, session_id, input_text, max_retries=3):
    retryable_errors = ['ThrottlingException', 'InternalServerException', 'ServiceQuotaExceededException']

    for attempt in range(max_retries):
        try:
            response = client.invoke_agent(...)
            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']

            if error_code not in retryable_errors:
                raise  # Don't retry validation/not found errors

            if attempt == max_retries - 1:
                raise  # Last attempt

            # Exponential backoff: 2^attempt * 100ms
            wait_time = (2 ** attempt) * 0.1
            time.sleep(wait_time)
```

**Alternatives Considered**:
- No retries: Rejected due to production reliability requirements
- Retry all errors: Rejected because some errors are permanent (validation, not found)
- AWS SDK retry only: Insufficient for Bedrock-specific retry logic

### 4. Structured Logging with JSON Format

**Decision**: Use Python's `logging` module with `json` library for structured output

**Rationale**:
- CloudWatch Logs Insights requires structured logs for filtering/querying
- Python's `logging` module is standard, no external dependencies
- JSON format enables queries like: `fields @timestamp, requestId, agentId | filter statusCode = 500`
- Lambda context provides `request_id` automatically

**Implementation Pattern**:
```python
import logging
import json
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_structured(level, message, **kwargs):
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        **kwargs
    }
    logger.log(getattr(logging, level.upper()), json.dumps(log_entry))

# Usage in handler
log_structured('info', 'Agent invocation started',
               requestId=context.request_id,
               agentId=agent_id,
               inputLength=len(input_text))
```

**Alternatives Considered**:
- python-json-logger library: Rejected to minimize dependencies
- Plain text logging: Rejected because CloudWatch Insights queries are difficult
- Custom logging framework: Rejected due to complexity

### 5. Input Validation Strategy

**Decision**: Use Python's built-in validation + regex for agent IDs

**Rationale**:
- Agent IDs follow AWS pattern: 10 alphanumeric characters (e.g., `ABCDE12345`)
- Agent alias IDs: Either 10 characters OR special values (`TSTALIASID`, `DRAFT`)
- Session IDs: UUID v4 format (36 characters with hyphens)
- Input text: Max 25KB (Bedrock limit)

**Validation Rules**:
```python
import re
import uuid

def validate_agent_id(agent_id: str) -> bool:
    # Agent ID: 10 alphanumeric characters
    return bool(re.match(r'^[A-Z0-9]{10}$', agent_id))

def validate_agent_alias_id(alias_id: str) -> bool:
    # Alias: 10 alphanumeric OR special values
    return (
        bool(re.match(r'^[A-Z0-9]{10}$', alias_id)) or
        alias_id in ['TSTALIASID', 'DRAFT']
    )

def validate_session_id(session_id: str) -> bool:
    # Optional, UUID v4 format
    if not session_id:
        return True  # Optional parameter
    try:
        uuid.UUID(session_id, version=4)
        return True
    except ValueError:
        return False

def validate_input_text(text: str) -> bool:
    # Max 25KB per Bedrock docs
    return len(text.encode('utf-8')) <= 25 * 1024
```

**Alternatives Considered**:
- pydantic validation: Rejected to minimize dependencies
- No validation: Rejected because Bedrock errors are less actionable than validation errors
- AWS SDK validation: Insufficient (happens after network call, wastes time/money)

### 6. Event Source Handling

**Decision**: Support multiple event formats with auto-detection

**Rationale**:
- Lambda can be triggered by API Gateway, EventBridge, direct invocation
- Each source has different event structure
- Auto-detect format, extract parameters, normalize to common interface

**Event Format Patterns**:

**Direct Invocation**:
```json
{
  "agentId": "ABCDE12345",
  "agentAliasId": "FGHIJ67890",
  "sessionId": "uuid-v4-here",
  "inputText": "User question"
}
```

**API Gateway**:
```json
{
  "body": "{\"agentId\":\"...\",\"inputText\":\"...\"}",
  "requestContext": {...}
}
```

**EventBridge**:
```json
{
  "detail": {
    "agentId": "...",
    "inputText": "..."
  }
}
```

**Implementation**:
```python
def parse_event(event):
    # Direct invocation
    if 'agentId' in event:
        return event

    # API Gateway
    if 'body' in event:
        import json
        return json.loads(event['body'])

    # EventBridge
    if 'detail' in event:
        return event['detail']

    raise ValueError('Unsupported event format')
```

**Alternatives Considered**:
- Single event format only: Rejected due to FR-012 (support multiple trigger sources)
- Separate handlers per source: Rejected because business logic is identical
- Event schema registry: Deferred to future enhancement

### 7. Response Streaming Handling

**Decision**: Collect all chunks and return complete response (no streaming to caller)

**Rationale**:
- Bedrock `invoke_agent` returns EventStream (chunked response)
- Lambda synchronous response doesn't support streaming to caller
- Must collect all chunks, concatenate, return as single response
- Future enhancement: Implement streaming via Lambda function URLs + response streaming

**Implementation Pattern**:
```python
def invoke_agent(agent_id, agent_alias_id, session_id, input_text):
    response = client.invoke_agent(...)

    output_text = ''
    citations = []
    trace_data = {}

    for event in response['completion']:
        if 'chunk' in event:
            chunk = event['chunk']
            if 'bytes' in chunk:
                output_text += chunk['bytes'].decode('utf-8')

        if 'trace' in event:
            trace_data = event['trace']

        if 'citation' in event:
            citations.append(event['citation'])

    return {
        'output': output_text,
        'citations': citations,
        'trace': trace_data,
        'sessionId': session_id
    }
```

**Alternatives Considered**:
- Stream directly to caller: Not supported by Lambda synchronous invocations
- Store chunks in S3: Overcomplicated for initial implementation
- Return first chunk only: Incomplete response, violates FR-003

### 8. Session Management

**Decision**: Pass `sessionId` through to Bedrock, let Bedrock manage session state

**Rationale**:
- Bedrock Agent Runtime handles session state internally
- Lambda is stateless (correct pattern)
- Caller provides `sessionId` for multi-turn conversations
- If no `sessionId` provided, Bedrock auto-generates one
- Lambda returns `sessionId` in response for caller to use in next invocation

**Session Flow**:
1. First call: No `sessionId` → Bedrock generates one → Return in response
2. Subsequent calls: Caller provides `sessionId` → Bedrock retrieves context → Maintains conversation

**Implementation**:
```python
# First invocation
response1 = invoke_agent(agent_id, alias_id, None, "Hello")
# response1 = {'output': '...', 'sessionId': 'generated-uuid'}

# Second invocation (conversation continues)
response2 = invoke_agent(agent_id, alias_id, response1['sessionId'], "Follow-up question")
```

**Alternatives Considered**:
- Store session state in DynamoDB: Rejected because Bedrock handles it
- No session support: Violates FR-004 (maintain session context)
- Custom session management: Duplicates Bedrock's built-in capability

## Technology Stack Summary

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Runtime | Python 3.13 | Matches project standard, modern Python features |
| AWS SDK | boto3 ≥1.34.0 | Official AWS SDK with Bedrock Agent Runtime support |
| Dependency Manager (Dev) | uv | Project standard, fast, reliable |
| Dependency Manager (Lambda) | pip via SAM | SAM convention, uses src/requirements.txt |
| Testing Framework | pytest + pytest-mock | Project standard, comprehensive mocking |
| Coverage Tool | pytest-cov | Project standard, enforces 80% threshold |
| Logging | Python logging + json | Built-in, structured, CloudWatch compatible |
| Validation | Built-in Python + regex | No external deps, sufficient for input validation |
| Retry Logic | botocore Config + custom | AWS native + Bedrock-specific error handling |
| Deployment | AWS SAM | Project standard, IaC for Lambda |

## Best Practices Applied

1. **Cold Start Optimization**:
   - Import boto3 at module level (reused across warm invocations)
   - Initialize client outside handler (connection pooling)
   - Lazy-load optional dependencies (json only when needed)

2. **Error Handling**:
   - Validate input before AWS calls (fail fast)
   - Distinguish permanent vs transient errors
   - Return actionable error messages to caller
   - Log full stack traces for debugging

3. **Security**:
   - No credentials in code (IAM role only)
   - Sanitize PII from logs (input/output text length only, not content)
   - Use least-privilege IAM permissions (`bedrock:InvokeAgent` only)
   - Validate all inputs (prevent injection attacks)

4. **Observability**:
   - Structured JSON logs (CloudWatch Insights compatible)
   - X-Ray tracing enabled (SAM Globals)
   - Log request ID, agent ID, duration, status
   - Include trace data from Bedrock in response

5. **Reliability**:
   - Idempotent design (same input → same output)
   - Graceful degradation (partial results when possible)
   - Retry with exponential backoff
   - Input validation prevents wasted Bedrock calls

## Open Questions / Future Enhancements

1. **Streaming**: Lambda function URLs support response streaming - consider for future enhancement
2. **Caching**: Should frequently-used agent responses be cached? (Deferred - measure need first)
3. **Rate limiting**: Should Lambda implement rate limiting per agent? (Deferred - use reserved concurrency)
4. **Multi-region**: Should function support multi-region Bedrock deployments? (Out of scope per spec)
5. **Agent discovery**: Should function validate agent exists before invocation? (Deferred - Bedrock returns clear error)

## Conclusion

All technical uncertainties resolved. Technology stack aligns with project standards (Python 3.13, boto3, uv, pytest, SAM). Implementation patterns follow AWS best practices for Lambda and Bedrock Agent Runtime. Ready to proceed to Phase 1 (Design & Contracts).
