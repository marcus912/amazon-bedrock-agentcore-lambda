# Data Model: Shared AgentCore Invocation Lambda

**Feature**: 001-shared-agent-invocation
**Phase**: 1 (Design & Contracts)
**Date**: 2025-11-11

## Overview

This document defines the data entities, validation rules, and state transitions for the AgentCore invocation Lambda function. The function is stateless - all entities represent request/response data structures, not persisted state.

## Core Entities

### 1. AgentInvocationRequest

**Purpose**: Encapsulates all parameters required to invoke a Bedrock AgentCore agent.

**Attributes**:
- `agentId` (string, required): AWS AgentCore agent identifier
  - Format: 10 alphanumeric characters (uppercase)
  - Example: `"ABCDE12345"`
  - Validation: Regex `^[A-Z0-9]{10}$`

- `agentAliasId` (string, required): Agent alias identifier
  - Format: 10 alphanumeric characters OR special values
  - Valid values: `^[A-Z0-9]{10}$` OR `"TSTALIASID"` OR `"DRAFT"`
  - Example: `"FGHIJ67890"` or `"TSTALIASID"`

- `sessionId` (string, optional): Session identifier for multi-turn conversations
  - Format: UUID v4 (36 characters with hyphens)
  - Example: `"123e4567-e89b-12d3-a456-426614174000"`
  - Validation: UUID v4 format
  - Default: If omitted, Bedrock auto-generates

- `inputText` (string, required): User input to send to the agent
  - Format: UTF-8 string
  - Max size: 25 KB (25,600 bytes)
  - Validation: Non-empty, ≤25KB encoded

- `timeout` (integer, optional): Override default timeout in seconds
  - Range: 1-60
  - Default: 30 seconds
  - Validation: Integer in range

- `maxRetries` (integer, optional): Override default retry count for transient errors
  - Range: 0-5
  - Default: 3
  - Validation: Integer in range

**Relationships**:
- Maps 1:1 to Bedrock `invoke_agent` API parameters
- Transformed from various event sources (API Gateway, EventBridge, direct)

**Validation Rules**:
1. `agentId` MUST be 10 uppercase alphanumeric characters
2. `agentAliasId` MUST be 10 alphanumeric characters OR special value
3. `sessionId` MUST be valid UUID v4 OR null
4. `inputText` MUST be non-empty AND ≤25KB when UTF-8 encoded
5. `timeout` IF provided MUST be integer 1-60
6. `maxRetries` IF provided MUST be integer 0-5

**Example JSON**:
```json
{
  "agentId": "ABCDE12345",
  "agentAliasId": "FGHIJ67890",
  "sessionId": "123e4567-e89b-12d3-a456-426614174000",
  "inputText": "What is the weather in San Francisco?",
  "timeout": 30,
  "maxRetries": 3
}
```

---

### 2. AgentInvocationResponse

**Purpose**: Encapsulates the complete result of an agent invocation, including output, metadata, and trace information.

**Attributes**:
- `data` (object, required): Primary response payload
  - `output` (string, required): Agent's generated response text
  - `sessionId` (string, required): Session ID for this conversation
  - `citations` (array, optional): Source citations used by agent
    - Each citation contains: `text`, `sourceUrl`, `retrievedReferences`
  - `trace` (object, optional): Bedrock trace data for debugging
    - Contains: reasoning, knowledge base queries, actions taken

- `metadata` (object, required): Response metadata
  - `requestId` (string, required): Lambda request ID for tracing
  - `timestamp` (string, required): ISO 8601 timestamp of response
  - `executionTimeMs` (integer, required): Handler execution time in milliseconds
  - `agentId` (string, required): Echo of requested agent ID
  - `tokenUsage` (object, optional): Token consumption metrics
    - `inputTokens` (integer): Tokens in user input
    - `outputTokens` (integer): Tokens in agent output

- `status` (string, required): Response status
  - Values: `"success"` | `"error"`
  - Determines structure of response

**Relationships**:
- Aggregates data from Bedrock EventStream response
- Maps to HTTP response for API Gateway
- Maps to EventBridge output for async processing

**Success Response Structure**:
```json
{
  "status": "success",
  "data": {
    "output": "The current weather in San Francisco is...",
    "sessionId": "123e4567-e89b-12d3-a456-426614174000",
    "citations": [
      {
        "text": "Weather data from...",
        "sourceUrl": "https://...",
        "retrievedReferences": [...]
      }
    ],
    "trace": {
      "reasoning": "...",
      "knowledgeBaseQueries": [...]
    }
  },
  "metadata": {
    "requestId": "lambda-request-id-here",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "executionTimeMs": 1250,
    "agentId": "ABCDE12345",
    "tokenUsage": {
      "inputTokens": 15,
      "outputTokens": 120
    }
  }
}
```

---

### 3. AgentInvocationError

**Purpose**: Standardized error response structure for failed invocations.

**Attributes**:
- `status` (string, required): Always `"error"`

- `errorType` (string, required): Error classification
  - Values:
    - `"ValidationError"`: Input validation failed
    - `"AgentNotFound"`: Agent/alias doesn't exist
    - `"ThrottlingError"`: Rate limit exceeded
    - `"TimeoutError"`: Invocation exceeded timeout
    - `"InternalError"`: AWS service error
    - `"UnknownError"`: Unclassified error

- `errorMessage` (string, required): Human-readable error description
  - Must be actionable (tell caller what to fix)
  - No internal stack traces (logged separately)
  - Example: `"Invalid agentId format. Expected 10 uppercase alphanumeric characters."`

- `errorCode` (string, optional): AWS error code if from Bedrock
  - Example: `"ResourceNotFoundException"`

- `metadata` (object, required): Error metadata
  - `requestId` (string, required): Lambda request ID for support
  - `timestamp` (string, required): ISO 8601 timestamp
  - `agentId` (string, optional): Requested agent ID (if validation passed)

- `retryable` (boolean, required): Whether caller should retry
  - `true`: Transient error (throttling, timeout, internal)
  - `false`: Permanent error (validation, not found)

**Error Response Structure**:
```json
{
  "status": "error",
  "errorType": "ValidationError",
  "errorMessage": "Invalid agentId format. Expected 10 uppercase alphanumeric characters.",
  "errorCode": null,
  "metadata": {
    "requestId": "lambda-request-id-here",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "agentId": "invalid-id"
  },
  "retryable": false
}
```

---

### 4. InvocationContext

**Purpose**: Internal entity tracking execution context and configuration for a single invocation. Not exposed in API.

**Attributes**:
- `requestId` (string, required): Lambda request ID from context
- `startTime` (float, required): Unix timestamp when handler started
- `config` (object, required): Handler configuration
  - `timeout`: Effective timeout for this invocation
  - `maxRetries`: Effective max retry count
  - `logLevel`: Logging verbosity
- `attempt` (integer, required): Current retry attempt (1-indexed)
- `errors` (array): List of errors encountered during retries

**Usage**: Passed through handler functions to track state and enable structured logging.

**Example (internal only)**:
```python
context = InvocationContext(
    requestId="aws-request-id",
    startTime=time.time(),
    config={'timeout': 30, 'maxRetries': 3, 'logLevel': 'INFO'},
    attempt=1,
    errors=[]
)
```

---

## Entity Relationships

```
┌─────────────────────────────────────┐
│     Lambda Event (API Gateway,      │
│     EventBridge, Direct)            │
└──────────────┬──────────────────────┘
               │ parse_event()
               ▼
┌─────────────────────────────────────┐
│   AgentInvocationRequest            │
│   (validated, normalized)           │
└──────────────┬──────────────────────┘
               │ invoke_agent()
               ▼
┌─────────────────────────────────────┐
│   Bedrock Agent Runtime API         │
│   (EventStream response)            │
└──────────────┬──────────────────────┘
               │ collect_chunks()
               ▼
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌─────────────┐   ┌─────────────────┐
│  Success?   │   │   Error?        │
│  Agent      │   │   Bedrock/      │
│  Response   │   │   Validation    │
└──────┬──────┘   └────────┬────────┘
       │                   │
       ▼                   ▼
┌─────────────────┐  ┌────────────────────┐
│ AgentInvocation │  │ AgentInvocation    │
│ Response        │  │ Error              │
│ (success)       │  │ (error)            │
└─────────────────┘  └────────────────────┘
```

---

## Validation Rules Summary

### Request Validation (Pre-Bedrock)
1. Validate `agentId` format (10 uppercase alphanumeric)
2. Validate `agentAliasId` format (10 alphanumeric OR special value)
3. Validate `sessionId` format (UUID v4 OR null)
4. Validate `inputText` non-empty and ≤25KB
5. Validate `timeout` in range 1-60 (if provided)
6. Validate `maxRetries` in range 0-5 (if provided)

**Validation Failure**: Return `AgentInvocationError` with `errorType="ValidationError"`, `retryable=false`

### Response Validation (Post-Bedrock)
1. Ensure EventStream contains at least one chunk
2. Concatenate all chunk bytes into complete output
3. Extract sessionId from response metadata
4. Collect all citations and trace data
5. Calculate execution time (end - start)

**Missing Data**: Log warning, return partial response with available data

---

## State Transitions

The Lambda function is **stateless**. However, the invocation process has the following logical states:

```
[START]
   ↓
[PARSE_EVENT] → Parse incoming event structure
   ↓
[VALIDATE_REQUEST] → Validate all input parameters
   ↓ (validation error)
   └─→ [ERROR_RESPONSE] → Return ValidationError
   ↓ (valid)
[INVOKE_AGENT] → Call Bedrock Agent Runtime API
   ↓ (throttling/transient error)
   └─→ [RETRY] → Wait (exponential backoff) → [INVOKE_AGENT]
   ↓ (permanent error)
   └─→ [ERROR_RESPONSE] → Return AgentNotFound/InternalError
   ↓ (success)
[COLLECT_CHUNKS] → Iterate EventStream, concatenate output
   ↓
[BUILD_RESPONSE] → Construct AgentInvocationResponse with metadata
   ↓
[RETURN]
```

**Error States**:
- Validation Error → Return immediately (no retry)
- Agent Not Found → Return immediately (no retry)
- Throttling → Retry with backoff (up to maxRetries)
- Timeout → Return error (no retry, caller can retry entire invocation)
- Internal Error → Retry with backoff (up to maxRetries)

---

## Data Transformations

### Event Source Transformations

**Direct Invocation** → AgentInvocationRequest:
```python
# Input: Direct event
{
  "agentId": "ABCDE12345",
  "inputText": "..."
}

# Output: AgentInvocationRequest (same structure)
```

**API Gateway** → AgentInvocationRequest:
```python
# Input: API Gateway event
{
  "body": "{\"agentId\":\"ABCDE12345\",\"inputText\":\"...\"}",
  "requestContext": {...}
}

# Output: AgentInvocationRequest
# Transformation: JSON.parse(event['body'])
```

**EventBridge** → AgentInvocationRequest:
```python
# Input: EventBridge event
{
  "detail": {
    "agentId": "ABCDE12345",
    "inputText": "..."
  }
}

# Output: AgentInvocationRequest
# Transformation: Extract event['detail']
```

### Bedrock Response → AgentInvocationResponse

```python
# Input: Bedrock EventStream
{
  'completion': [
    {'chunk': {'bytes': b'Hello'}},
    {'chunk': {'bytes': b' world'}},
    {'trace': {...}},
    {'citation': {...}}
  ]
}

# Output: AgentInvocationResponse
{
  "data": {
    "output": "Hello world",  # Concatenated chunks
    "sessionId": "...",        # From Bedrock metadata
    "citations": [...],        # Collected citations
    "trace": {...}             # Collected trace
  },
  "metadata": {
    "requestId": "...",
    "timestamp": "...",
    "executionTimeMs": 1250,
    "agentId": "ABCDE12345"
  }
}
```

---

## Persistence

**None**: Lambda function is stateless. No data persisted to database or S3.

**Session State**: Managed by Bedrock service (passed via `sessionId`, not stored by Lambda)

**Logs**: Structured JSON logs persisted to CloudWatch Logs (15-day retention recommended)

**Traces**: X-Ray traces persisted to AWS X-Ray (24-hour retention default)

---

## Conclusion

Data model defines 4 core entities: `AgentInvocationRequest`, `AgentInvocationResponse`, `AgentInvocationError`, and `InvocationContext`. All validation rules specified. State transitions documented (stateless function with logical invocation states). Ready to proceed to contract generation (Phase 1 continued).
