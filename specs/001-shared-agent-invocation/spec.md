# Feature Specification: Shared AgentCore Invocation Module

**Feature Branch**: `001-shared-agent-invocation`
**Created**: 2025-11-11
**Updated**: 2025-11-11 (Architecture revised to shared module)
**Status**: Draft - Architecture Updated
**Input**: User description: "Create a shared Python module for invoking Bedrock AgentCore agents. Multiple Lambda handlers (like the existing SQS email handler) will import and use this shared module by passing prompt text and session parameters. The agent ARN should be configurable via environment variables (AGENT_ARN, AGENT_ALIAS_ARN). Include SQS test event for testing the integration."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Shared Module Integration (Priority: P1)

A Lambda handler developer needs to invoke a Bedrock AgentCore agent from within their handler function. They import the shared agent invocation module, pass the prompt text and optional session ID, and receive the agent's response synchronously.

**Why this priority**: This is the foundational functionality - providing a reusable Python module that any Lambda handler can import and use. Without this, handlers cannot invoke agents.

**Independent Test**: Import the module in the existing SQS email handler, call `invoke_agent()` with a test prompt, verify the agent response is returned, and confirm email processing continues with the enriched data.

**Acceptance Scenarios**:

1. **Given** the SQS email handler receives an email event, **When** it imports the shared module and calls `invoke_agent(prompt="Summarize this email", session_id=None)`, **Then** the agent processes the prompt and returns a summary response
2. **Given** a handler wants to maintain conversation context, **When** it calls `invoke_agent(prompt="Follow-up question", session_id="existing-uuid")`, **Then** the agent retrieves previous context and provides a contextual response
3. **Given** multiple handlers invoke agents concurrently, **When** they each call the shared module independently, **Then** each invocation completes without interference and returns correct results

---

### User Story 2 - Environment-Based Configuration (Priority: P1)

Operations teams need to configure which Bedrock agent is invoked by setting environment variables, without changing code. Different environments (dev, staging, prod) use different agent ARNs configured via SAM template parameters.

**Why this priority**: Configuration management is critical for multi-environment deployments and changing agents without code redeployment.

**Independent Test**: Deploy with AGENT_ARN set to a test agent in dev environment, verify invocations use that agent. Change environment variable and redeploy, verify new agent is used.

**Acceptance Scenarios**:

1. **Given** AGENT_ARN and AGENT_ALIAS_ARN are set in Lambda environment variables, **When** the shared module is imported, **Then** it reads these values and uses them for all agent invocations
2. **Given** dev environment has AGENT_ARN=arn:aws:bedrock:us-west-2:123456789012:agent/TESTDEV123 and prod has AGENT_ARN=arn:aws:bedrock:us-west-2:123456789012:agent/PRODABC789, **When** the same code is deployed to both environments, **Then** each environment invokes its respective agent
3. **Given** AGENT_ARN or AGENT_ALIAS_ARN environment variables are missing, **When** the module is imported, **Then** it raises a clear configuration error at startup

---

### User Story 3 - Error Handling for Callers (Priority: P2)

Handler developers need clear error messages when agent invocations fail, so they can handle errors gracefully in their Lambda handler logic (retry, log, return error to caller).

**Why this priority**: Robust error handling ensures handlers can implement appropriate error recovery strategies without the shared module obscuring failure details.

**Independent Test**: Call `invoke_agent()` with invalid prompt or during Bedrock service issues, verify appropriate exception is raised with actionable error message.

**Acceptance Scenarios**:

1. **Given** the agent is unavailable (deleted or region issue), **When** a handler calls `invoke_agent()`, **Then** an `AgentNotFoundException` is raised with the agent ARN in the error message
2. **Given** Bedrock throttles requests, **When** a handler calls `invoke_agent()`, **Then** the module retries with exponential backoff (up to 3 attempts) and either succeeds or raises `ThrottlingException` with retry details
3. **Given** the prompt exceeds Bedrock's input limit, **When** a handler calls `invoke_agent()`, **Then** a `ValidationException` is raised immediately with the size limit and actual size

---

### User Story 4 - SQS Integration Testing (Priority: P2)

Developers need SQS test events to verify the shared module integrates correctly with SQS-triggered handlers, ensuring agent invocations work end-to-end from SQS message receipt.

**Why this priority**: SQS is a primary trigger source for Lambda handlers. Test events enable local and integration testing without live SQS queues.

**Independent Test**: Run `sam local invoke` with an SQS test event, verify the handler processes the SQS message, invokes the agent via the shared module, and returns a successful response.

**Acceptance Scenarios**:

1. **Given** an SQS test event with a message containing "email body to summarize", **When** the test event is used with `sam local invoke`, **Then** the SQS email handler invokes the agent and processes the summary response
2. **Given** multiple SQS messages in a batch event, **When** the handler processes the batch, **Then** the shared module handles concurrent agent invocations for each message independently
3. **Given** an SQS test event triggers an agent invocation that fails, **When** the handler catches the exception, **Then** the handler can return a partial batch failure to SQS for retry

---

### Edge Cases

- What happens when AGENT_ARN is set but the agent doesn't exist in that region?
- How does the module behave when called before Lambda environment variables are available?
- What happens when multiple handlers import the module simultaneously (cold start scenario)?
- How does the module handle prompts with special characters or non-UTF-8 encoding?
- What happens when the agent response is empty or malformed?
- How does session management work if the same session_id is used across different handlers?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Module MUST provide an `invoke_agent(prompt, session_id=None, **kwargs)` function that accepts prompt text and optional session ID
- **FR-002**: Module MUST read AGENT_ARN and AGENT_ALIAS_ARN from os.environ at import time and use these for all invocations
- **FR-003**: Module MUST raise ConfigurationError if AGENT_ARN or AGENT_ALIAS_ARN environment variables are not set
- **FR-004**: Module MUST call the Bedrock Agent Runtime API `invoke_agent` operation with the configured agent ARN
- **FR-005**: Module MUST collect all EventStream chunks from Bedrock and return the complete agent response as a string
- **FR-006**: Module MUST handle session context by passing session_id to Bedrock if provided, or allowing Bedrock to generate one
- **FR-007**: Module MUST implement retry logic with exponential backoff for transient errors (ThrottlingException, InternalServerException) up to 3 attempts
- **FR-008**: Module MUST NOT retry permanent errors (ResourceNotFoundException, ValidationException) and raise immediately
- **FR-009**: Module MUST raise domain-specific exceptions (AgentNotFoundException, ThrottlingException, ValidationException) with actionable error messages
- **FR-010**: Module MUST sanitize sensitive data from error messages (only include agent ARN, not credentials or session tokens)
- **FR-011**: Module MUST be importable from any Lambda handler (no side effects on import except environment variable reading)
- **FR-012**: Module MUST support concurrent invocations from multiple handlers or threads (thread-safe client initialization)
- **FR-013**: Module MUST validate prompt is non-empty string before calling Bedrock
- **FR-014**: Module MUST validate session_id is None or valid UUID v4 format
- **FR-015**: Module MUST log invocation details (prompt length, session ID presence, agent ARN, execution time) at INFO level

### Key Entities

- **AgentInvocationRequest**: Prompt text (string), session ID (optional UUID v4), agent ARN (from environment), agent alias ARN (from environment), additional kwargs (timeout, max_retries)
- **AgentInvocationResponse**: Agent output text (string), session ID (returned by Bedrock), execution time (milliseconds), token usage (if available from Bedrock)
- **AgentInvocationError**: Error type (configuration, validation, throttling, not found, internal), error message (actionable), agent ARN (for context), retry attempts (if applicable)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Any Lambda handler can import the module and invoke agents with a single function call taking under 5 lines of code
- **SC-002**: Agent invocations from the shared module complete within 30 seconds for 95% of requests (measured from module function entry to return)
- **SC-003**: The module handles 100+ concurrent agent invocations from different handlers without errors or resource contention
- **SC-004**: 90% of transient errors (throttling, temporary failures) result in successful retries within 3 attempts
- **SC-005**: Configuration errors (missing AGENT_ARN) are detected at Lambda cold start and prevent handler execution with clear error messages
- **SC-006**: Module function calls are observable through CloudWatch Logs with structured logging showing prompt length, agent ARN, execution time, and outcome
- **SC-007**: Unit test coverage of the shared module exceeds 80% with tests for success paths, error paths, and edge cases

## Assumptions *(optional)*

- Lambda handlers run in Python 3.13 runtime (consistent with existing handlers)
- boto3 library with Bedrock Agent Runtime support is available in the Lambda environment
- Each Lambda function has AGENT_ARN and AGENT_ALIAS_ARN set as environment variables in the SAM template
- Handlers importing the module handle exceptions appropriately (module raises, doesn't suppress errors)
- Session management is stateless from the module's perspective (session IDs passed by callers, state managed by Bedrock)
- Module does not persist any state between invocations (stateless design)
- Handlers are responsible for logging their own business logic; module logs only agent invocation details
- The same agent ARN is used for all invocations within a single Lambda function (environment variable per function)

## Dependencies *(optional)*

- Amazon Bedrock service available in deployment region
- AgentCore agents pre-created with ARNs configured in environment variables
- boto3 >= 1.34.0 (Bedrock AgentCore support)
- Lambda execution role with `bedrock-agentcore:InvokeAgentRuntime` permission (for bedrock-agentcore client)
- Python logging module for structured logging
- uuid and re modules for validation (Python standard library)

## Scope Boundaries *(optional)*

### In Scope

- Shared Python module with `invoke_agent()` function
- Environment variable configuration (AGENT_ARN, AGENT_ALIAS_ARN)
- Error handling with domain-specific exceptions
- Retry logic for transient failures
- Input validation (prompt, session ID)
- Structured logging of invocations
- Thread-safe design for concurrent use
- SQS test event for integration testing
- Unit tests with mocked Bedrock responses

### Out of Scope

- Standalone Lambda handler (module is imported, not invoked directly)
- API Gateway or EventBridge integration (handlers' responsibility)
- Agent creation or management (agents must exist)
- Environment variable injection into SAM template (configuration management concern)
- Handler-specific business logic (email parsing, response formatting, etc.)
- Response caching or optimization
- Custom session storage (Bedrock manages sessions)
- Multi-region agent failover
- Agent response streaming (returns complete response only)
- Authentication/authorization logic (IAM role handles permissions)

## Notes

**Architecture Change from Original Spec**:

This specification revises the architecture from a standalone Lambda handler to a **shared Python module**. The original design (direct agent invocation handler) is replaced with a library pattern where multiple handlers import and use the module.

**Key Architectural Differences**:
- **Original**: Single Lambda handler with `lambda_handler()` function receiving events directly
- **Revised**: Shared module with `invoke_agent()` function called by multiple handlers
- **Original**: Event parsing for API Gateway/EventBridge/direct invocation
- **Revised**: Simple function interface (prompt + session_id) - no event parsing
- **Original**: Standalone deployment with SAM resource
- **Revised**: Module deployed alongside existing handlers (shared code)

**Migration Path**:
If implementing both patterns:
1. Create shared module first (this spec)
2. Existing handlers import and use the module
3. Optionally create standalone handler that uses the same module (future enhancement)
