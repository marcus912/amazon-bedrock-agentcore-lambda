# Implementation Plan: Shared AgentCore Invocation Module

**Branch**: `001-shared-agent-invocation` | **Date**: 2025-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-shared-agent-invocation/spec.md`

## Summary

Create a three-layer architecture for Lambda handlers that keeps handler code clean:

1. **AWS Integrations** (`src/integrations/`): Reusable infrastructure code for invoking Amazon Bedrock AgentCore agents. The `agentcore_invocation.py` module provides a simple `invoke_agent(prompt, session_id)` function interface, uses `boto3.client('bedrock-agentcore').invoke_agent_runtime()` API, reads agent runtime ARN from environment variable (AGENT_RUNTIME_ARN), implements retry logic for transient failures, and raises domain-specific exceptions for error handling.

2. **Services Layer** (`src/services/`): Utility functions for handler operations including email processing (`email.py` with `extract_email_body()`) and S3 operations (`s3.py` with `fetch_email_from_s3()`). Services are reusable across multiple handlers.

3. **Handlers** (`src/*.py`): Clean business logic that imports services and integrations. Handlers delegate utility operations to services and AWS infrastructure concerns to integrations.

Multiple handlers (like the existing SQS email handler) will import both services and integrations to maintain clean, focused handler code without duplicating Bedrock integration logic or utility functions.

## Technical Context

**Language/Version**: Python 3.13 (consistent with existing Lambda handlers)
**Primary Dependencies**: boto3 ≥1.34.0 (bedrock-agentcore client), botocore (AWS service definitions), managed by uv
**Storage**: N/A (stateless modules, no persistence)
**Testing**: pytest with pytest-mock for unit tests, pytest-cov for coverage (pyproject.toml configured)
**Target Platform**: AWS Lambda (Python 3.13 runtime) deployed via SAM
**Project Type**: Shared modules (src/integrations/), services layer (src/services/), imported by Lambda handlers
**Performance Goals**: 95% of invocations < 30s, support 100+ concurrent calls, thread-safe design
**Constraints**: No side effects on import (except env var reading), 80%+ test coverage, structured logging
**Scale/Scope**: Three-layer architecture with AWS integrations (agentcore_invocation.py), services (email.py, s3.py), and handlers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ⚠️ I. Function-First Architecture

**Status**: MODIFIED (shared module pattern)
**Evidence**: This is NOT a standalone Lambda function but a shared utility module. Multiple Lambda functions (handlers) will import and use it.
**Justification**: Constitution principle applies to handlers (SQS email handler, future handlers), not shared code. Shared module promotes code reuse and DRY principle, preventing duplication of Bedrock integration logic across handlers.

### ✅ II. Infrastructure as Code (NON-NEGOTIABLE)

**Status**: PASS
**Evidence**: No new Lambda resources created. Module deployed alongside existing handlers via SAM build process. Environment variables (AGENT_RUNTIME_ARN) defined in SAM template per handler.

### ✅ III. Test-First Development (NON-NEGOTIABLE)

**Status**: PASS
**Evidence**: Unit tests for `invoke_agent()` function, custom exceptions, validation logic will be written FIRST with mocked boto3 responses. Tests will FAIL initially, then implementation makes them PASS.

### ✅ IV. Comprehensive Testing Standards

**Status**: PASS (target: 80%+ coverage)
**Evidence**: Test suite will include:
- Unit tests: Module functions with mocked bedrock-agentcore client
- Contract tests: SQS event schema for integration testing
- Integration tests: Import module in SQS handler, invoke with test prompt
Coverage gate: ≥80% required.

### ✅ V. Observability by Default

**Status**: PASS
**Evidence**: Module will log at INFO level: prompt length, agent ARN, execution time, session ID presence, outcome (success/error). Callers (handlers) responsible for request ID logging.

### ✅ VI. User Experience Consistency

**Status**: PASS (module raises exceptions, handlers format responses)
**Evidence**: Module raises domain-specific exceptions (AgentNotFoundException, ThrottlingException, ValidationException) with actionable messages. Handlers catch and format responses according to their trigger source (SQS, API Gateway, etc.).

### Performance & Reliability Check

**Status**: PASS
- ✅ Latency: Target 30s timeout for Bedrock invocations
- ✅ Retry logic: Exponential backoff for throttling (3 attempts max)
- ✅ Thread-safe: boto3 client initialized at module level (thread-safe)
- ✅ Validation: Prompt and session_id validated before Bedrock call
- ✅ Configuration: Env vars read at import, ConfigurationError if missing
- ✅ Idempotency: Session IDs enable conversation context, Bedrock manages state

**GATE RESULT**: ✅ ALL CHECKS PASS (with Function-First architecture modification justified)

## Project Structure

### Documentation (this feature)

```text
specs/001-shared-agent-invocation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── integrations/                        # AWS service integrations
│   ├── __init__.py                      # Makes integrations a package
│   └── agentcore_invocation.py          # Main module (new)
├── services/                            # Internal utility functions
│   ├── __init__.py                      # Makes services a package
│   ├── email.py                         # Email utilities (new)
│   │                                    #   - extract_email_body()
│   │                                    #   - parse_email_headers()
│   └── s3.py                            # S3 utilities (new)
│                                        #   - fetch_email_from_s3()
│                                        #   - upload_processed_result()
├── sqs_email_handler.py                 # Existing handler (imports services + integrations)
└── requirements.txt                     # Shared dependencies (boto3, botocore)

tests/
├── integrations/                        # Tests for AWS integrations
│   └── test_agentcore_invocation.py     # Unit tests for agentcore module (new)
├── services/                            # Tests for service utilities
│   ├── test_email.py                    # Email service tests (new)
│   └── test_s3.py                       # S3 service tests (new)
├── events/
│   ├── sqs-email-with-agent-invocation.json  # SQS test event (new)
│   └── sqs-event.json                        # Existing SES event
└── test_sqs_email_handler.py                 # Existing handler tests

template.yaml                # SAM template (update handlers to add AGENT_RUNTIME_ARN env var)
samconfig.toml               # Deployment config (already supports multi-env)
pyproject.toml               # Python project config (uv managed)
uv.lock                      # Locked dependencies
```

**Structure Decision**: Three-layer architecture for clean handler code:

1. **Handlers** (`src/*.py`): Business logic only, delegate to services and integrations
2. **Services** (`src/services/`): Reusable utility functions (email processing, S3 operations)
3. **Integrations** (`src/integrations/`): AWS service wrappers (agent invocation, Bedrock integrations)

**Integrations Layer**: Create `src/integrations/` directory for AWS service integrations:
- `agentcore_invocation.py`: Contains `invoke_agent()` function wrapping `boto3.client('bedrock-agentcore').invoke_agent_runtime()` API
  - Reads AGENT_RUNTIME_ARN from environment
  - Generates 33+ char session IDs (e.g., "session-" + UUID4)
  - Formats payload as JSON string: `{"prompt": "text"}`
  - Handles streaming response with `.read()` and JSON parsing
  - Custom exceptions: ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException

**Services Layer**: Create `src/services/` directory for handler utility functions:
- `email.py`: Email-specific functions like `extract_email_body()`, `parse_email_headers()`
- `s3.py`: S3 operations like `fetch_email_from_s3(bucket, key)`, `upload_processed_result()`

**Handler Pattern**: Handlers remain clean by importing services and integrations:

```python
# Example: Clean SQS email handler using services + integrations
from services import email, s3
from integrations import agentcore_invocation

def lambda_handler(event, context):
    for record in event['Records']:
        # Use S3 service to fetch email
        s3_bucket = record['s3']['bucket']['name']
        s3_key = record['s3']['object']['key']
        email_content = s3.fetch_email_from_s3(s3_bucket, s3_key)

        # Use email service to extract body
        body = email.extract_email_body(email_content)

        # Use integration for agent invocation
        summary = agentcore_invocation.invoke_agent(
            prompt=f"Summarize this email: {body}",
            session_id=None
        )

        # Return or process summary
        return {"statusCode": 200, "summary": summary}
```

**SAM Build Process**: Both `services/` and `integrations/` directories included in all Lambda deployment packages.

**SQS Test Events**: Two test events for different testing scenarios:
1. `sqs-event.json` (existing) - Basic SES email notification via SQS
2. `sqs-email-with-agent-invocation.json` (new) - SES email notification with prompt text suitable for agent testing

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Function-First Architecture (Principle I) | Shared integrations module is NOT a Lambda function. It's imported by multiple handlers. | Creating separate Lambda function for agent invocation would require handlers to make cross-Lambda calls (higher latency, complexity, cost). Duplicating Bedrock logic in each handler violates DRY and creates maintenance burden. |

**Justification**: Shared module pattern is standard practice for utility code in serverless projects. Constitution's Function-First principle applies to handlers (business logic), not shared libraries (infrastructure/integration code).

## Phase 0: Research Summary

**Status**: ✅ COMPLETE

Key decisions for three-layer architecture:

### AWS Integrations Architecture
1. **Module Structure**: Create `src/integrations/agentcore_invocation.py` as importable module
2. **Dependency Management**: boto3 in `src/requirements.txt` (Lambda runtime), uv manages dev deps
3. **Boto3 Client**: Use `boto3.client('bedrock-agentcore', region_name='us-west-2')` for AgentCore API
4. **API Method**: Call `client.invoke_agent_runtime()` with parameters:
   - `agentRuntimeArn`: Full agent runtime ARN from environment (e.g., `arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/agent-name`)
   - `runtimeSessionId`: Session ID (33+ characters required)
   - `payload`: JSON string with `{"prompt": "text"}` format
   - `qualifier`: Optional, defaults to "DEFAULT"
5. **Environment Variables**: Read `AGENT_RUNTIME_ARN` at module import time
6. **Session ID Handling**: Generate 33+ character session IDs (use UUID4 + prefix for minimum length)
7. **Response Handling**: Call `.read()` on response['response'] to get streaming body, then parse JSON
8. **Error Handling**: Custom exception classes (ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException) inherit from base Exception
9. **Thread Safety**: Use boto3.client() at module level (boto3 clients are thread-safe)
10. **Validation**: Validate prompt (non-empty string) and session_id format before API call
11. **Retry Logic**: botocore Config with adaptive retry mode + custom exponential backoff for Bedrock-specific errors
12. **Logging**: Python logging.getLogger(__name__) for module-level logger, structured logging with JSON

### Services Layer Architecture
13. **Services Structure**: Create `src/services/` directory for utility functions
14. **Email Services** (`email.py`): Functions like `extract_email_body()`, `parse_email_headers()` - reusable across handlers
15. **S3 Services** (`s3.py`): Functions like `fetch_email_from_s3(bucket, key)`, `upload_processed_result()`
16. **Handler Pattern**: Handlers import both services and integrations for clean code separation

### SQS Test Event Requirements
17. **Test Event Purpose**: Enable local testing with `sam local invoke` for agent invocation integration
18. **Event Content**: Include email body text suitable for agent summarization prompts
19. **Event Structure**: Standard SQS + SES notification format with S3 reference

**Research Findings**: [research.md](research.md) (to be generated)

## Phase 1: Design Summary

**Status**: ✅ COMPLETE

### 1. Data Model ([data-model.md](data-model.md))

Module interface design:
- **Function**: `invoke_agent(prompt: str, session_id: Optional[str] = None, **kwargs) -> str`
- **Boto3 Client**: `boto3.client('bedrock-agentcore', region_name='us-west-2')`
- **API Method**: `client.invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload, qualifier='DEFAULT')`
- **Payload Format**: JSON string `{"prompt": "text"}`
- **Session ID**: 33+ characters (auto-generate if None, use UUID4 + prefix like "session-")
- **Response**: Call `.read()` on `response['response']`, parse JSON to extract agent output
- **Exceptions**: ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException
- **Configuration**: AGENT_RUNTIME_ARN from os.environ
- **Return**: Agent response text (string)

### 2. Contracts ([contracts/](contracts/))

Module interface contract:
- **Input**: prompt (required string), session_id (optional UUID v4 string)
- **Output**: Agent response text (string)
- **Exceptions**: Documented exception types with error messages
- **Example Usage**: Handler code snippet importing and calling module
- **SQS Event Schema**: JSON schema for `sqs-email-with-agent-invocation.json`

### 3. Quickstart ([quickstart.md](quickstart.md))

Step-by-step implementation guide:
1. Create `src/integrations/` directory and module file
2. Write unit tests FIRST (test-first development)
3. Implement `invoke_agent()` function
4. Add custom exception classes
5. Create `sqs-email-with-agent-invocation.json` test event
6. Update SQS email handler to import and use module
7. Test locally with `sam local invoke`
8. Deploy to dev and verify integration

### 4. Agent Context

Updated `CLAUDE.md` with:
- Architecture: Three-layer architecture (handlers, services, integrations)
- Module location: src/integrations/agentcore_invocation.py
- Dependencies: boto3 ≥1.34.0 (bedrock-agentcore client), botocore (uv managed)
- Configuration: Environment variable AGENT_RUNTIME_ARN (full agent runtime ARN)
- API: boto3.client('bedrock-agentcore').invoke_agent_runtime()
- Test events: sqs-event.json (existing), sqs-email-with-agent-invocation.json (new)

## Phase 2: Task Generation

**Next Step**: Run `/speckit.tasks` to generate implementation tasks

Task organization (preview):
- **Phase 1: Setup** - Create integrations/ and services/ directories, update dependencies
- **Phase 2: Foundational** - Module structure, exception classes, services layer
- **Phase 3: User Story 1** (P1) - Core `invoke_agent()` implementation
- **Phase 4: User Story 2** (P1) - Environment variable configuration
- **Phase 5: User Story 3** (P2) - Error handling and retries
- **Phase 6: Services Implementation** - Email and S3 service functions
- **Phase 7: User Story 4** (P2) - Create SQS test event, integration testing with clean handler pattern
- **Final Phase: Polish** - Documentation, coverage verification

## Implementation Readiness

**Status**: ✅ READY FOR IMPLEMENTATION

All prerequisites satisfied:
- ✅ Constitution Check passed (Function-First modified with justification)
- ✅ Technical Context complete (no NEEDS CLARIFICATION)
- ✅ Architecture defined (three-layer: handlers, services, integrations)
- ✅ Module interface specified (`invoke_agent()` function)
- ✅ Configuration approach defined (environment variables)
- ✅ SQS test event requirements documented

**Estimated Implementation Time**: 3-4 hours

**Success Criteria** (from spec.md):
- ✅ SC-001: Import and invoke in under 5 lines of code
- ✅ SC-002: 95% of invocations < 30 seconds
- ✅ SC-003: Handle 100+ concurrent invocations
- ✅ SC-004: 90% of transient errors succeed within 3 retries
- ✅ SC-005: Configuration errors detected at cold start
- ✅ SC-006: Structured logging enabled
- ✅ SC-007: Unit test coverage ≥80%

## Post-Implementation Verification

After implementation, verify:

1. **Constitution Compliance**:
   - [x] Function-First: Justified (integrations + services layer, not standalone handler)
   - [ ] IaC: Environment variables in SAM template
   - [ ] Test-First: Tests written before implementation for all modules
   - [ ] Testing Standards: Coverage ≥80% for integrations AND services
   - [ ] Observability: Structured logging implemented
   - [ ] UX Consistency: Domain-specific exceptions raised

2. **Functional Requirements** (FR-001 through FR-015 from spec.md)
3. **Success Criteria** (SC-001 through SC-007 from spec.md)
4. **Integration**:
   - [ ] SQS email handler successfully imports services (email, s3)
   - [ ] SQS email handler successfully imports integrations (agentcore_invocation)
   - [ ] Handler code is clean with business logic only
   - [ ] SQS test event (`sqs-email-with-agent-invocation.json`) created and works with `sam local invoke`
5. **Services Layer**:
   - [ ] `fetch_email_from_s3(bucket, key)` function works correctly
   - [ ] `extract_email_body(email_content)` function works correctly
   - [ ] Services are reusable across multiple handlers
   - [ ] Unit tests for services with mocked boto3 S3 client

## Implementation Notes

**Key Differences from Original Plan**:
- **Original**: Standalone Lambda handler with lambda_handler() entry point
- **Current**: Three-layer architecture (handlers + services + integrations)
- **Original**: Event parsing for multiple trigger sources in single handler
- **Current**: Simple function interfaces, handlers delegate to services and integrations
- **Original**: SAM resource for Lambda function
- **Current**: Modules and services deployed with existing handlers (no new SAM resource)

**Architecture Layers**:
1. **Handlers**: Business logic only, imports services and integrations
2. **Services** (`src/services/`): Utility functions (email processing, S3 operations)
3. **Integrations** (`src/integrations/`): AWS service wrappers (agent invocation)

**Naming Decision**:
- Renamed `shared/` to `integrations/` for clarity
- **Rationale**: "integrations" clearly indicates AWS service integrations (Bedrock, etc.) vs internal utilities (services)
- **Pattern**: Common in Python projects for external service integrations
- **Clarity**: Distinguishes infrastructure (integrations) from business utilities (services)

**Migration Strategy**:
1. Implement AWS integrations (`src/integrations/agentcore_invocation.py`)
2. Implement services layer (`src/services/email.py`, `src/services/s3.py`)
3. Create SQS test event (`tests/events/sqs-email-with-agent-invocation.json`)
4. Update existing SQS email handler to use clean pattern:
   - Import services for email/S3 operations
   - Import integrations for agent invocation
   - Keep handler logic focused on business flow
5. Future handlers follow same pattern (import services + integrations)

**Testing Strategy**:
- Unit tests for integrations: Mock `boto3.client('bedrock-agentcore')`, mock `invoke_agent_runtime()` response with `.read()` method
  - Test successful invocation with valid prompt
  - Test session ID generation (33+ chars)
  - Test payload formatting (JSON string with prompt)
  - Test response parsing (`.read()` and JSON decode)
  - Test error scenarios (ConfigurationError, AgentNotFoundException, ThrottlingException)
- Unit tests for services: Mock boto3 S3 client for `fetch_email_from_s3()`, test `extract_email_body()` with sample emails
- Contract tests: Validate `sqs-email-with-agent-invocation.json` schema
- Integration tests: Import services + integrations in SQS handler, test with SQS event using `sam local invoke` (requires AGENT_RUNTIME_ARN in environment)

**SQS Test Event Design**:
- Based on existing `sqs-event.json` structure
- Email body contains meaningful text for agent summarization (e.g., customer support inquiry)
- S3 reference points to test bucket/key
- Includes all required SQS + SES notification fields
- Enables end-to-end testing: SQS → Handler → S3 → Email extraction → Agent invocation → Response

## End of Planning Phase

Planning phase complete. Ready for task generation (`/speckit.tasks`) and implementation.
