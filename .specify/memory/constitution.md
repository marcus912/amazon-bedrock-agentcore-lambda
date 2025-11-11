<!--
SYNC IMPACT REPORT
==================
Version Change: NEW (no prior version) → 1.0.0
Modified Principles: N/A (initial creation)
Added Sections:
  - Core Principles (all 6 principles)
  - Performance & Reliability Standards
  - Development Workflow
  - Governance

Templates Requiring Updates:
  ✅ plan-template.md - Constitution Check section ready for validation
  ✅ spec-template.md - Aligned with testability and user-focused requirements
  ✅ tasks-template.md - Supports test-first and independent story testing

Follow-up TODOs: None (all placeholders filled)

Rationale for Version 1.0.0:
  - Initial constitution ratification for Amazon Bedrock AgentCore Lambda Functions project
  - Establishes baseline governance for code quality, testing, UX, and performance
  - MINOR would be inappropriate as this is the founding document
-->

# Amazon Bedrock AgentCore Lambda Functions Constitution

## Core Principles

### I. Function-First Architecture

Every feature MUST be implemented as an independent Lambda function. Lambda functions MUST be self-contained, independently testable, and deployable. Each function MUST have a clear, single purpose - no organizational-only functions without concrete business value.

**Rationale**: Serverless architecture demands clear separation of concerns. Independent functions enable parallel development, isolated testing, and granular scaling. This prevents monolithic Lambda anti-patterns that defeat serverless benefits.

### II. Infrastructure as Code (NON-NEGOTIABLE)

All Lambda functions, IAM roles, event sources, and AWS resources MUST be defined in SAM template.yaml. Manual console changes are PROHIBITED. Environment-specific configurations MUST be parameterized in samconfig.toml (dev, staging, prod).

**Rationale**: Manual changes create drift, break reproducibility, and cause deployment failures. IaC ensures every environment is identical except for explicit parameters. This is non-negotiable for production reliability.

### III. Test-First Development (NON-NEGOTIABLE)

Tests MUST be written BEFORE implementation for all Lambda handlers. Test sequence:
1. Write unit tests with mocked AWS services → tests FAIL
2. Get user/stakeholder approval on test scenarios
3. Implement handler → tests PASS
4. Red-Green-Refactor cycle strictly enforced

**Rationale**: Lambda functions are difficult to debug in production. Test-first ensures handlers are designed for testability from the start, prevents untestable code patterns, and creates living documentation of expected behavior.

### IV. Comprehensive Testing Standards

Every Lambda function MUST achieve minimum 80% code coverage. Test suite MUST include:
- **Unit tests**: All handler logic with mocked boto3 clients (pytest-mock)
- **Contract tests**: Event schema validation (test events in tests/events/)
- **Integration tests**: End-to-end flows with localstack or live AWS resources (dev only)

Coverage below 80% BLOCKS pull request merging. Tests MUST be fast (<5s per function suite).

**Rationale**: Lambda functions have hidden dependencies (IAM, event schemas, AWS service behavior). Multi-layer testing catches integration issues before deployment. 80% threshold balances thoroughness with pragmatism.

### V. Observability by Default

Every Lambda function MUST implement structured logging using Python's logging module with JSON formatting. X-Ray tracing MUST be enabled (already configured in SAM Globals). All handlers MUST log:
- Request ID (from Lambda context)
- Input event size and type
- Execution duration
- Success/error outcome with stack traces

PII and secrets MUST be sanitized from logs. CloudWatch log retention MUST be configured explicitly.

**Rationale**: Serverless debugging requires rich telemetry. Structured logs enable CloudWatch Insights queries. X-Ray traces reveal performance bottlenecks across AWS services. Without observability, production issues become untraceable.

### VI. User Experience Consistency

Lambda responses MUST follow consistent patterns:
- **Success**: Return structured JSON with data, metadata (requestId, timestamp)
- **Error**: Return structured error JSON with errorType, errorMessage, requestId
- **HTTP responses** (API Gateway): Use standard status codes (200, 400, 404, 500)
- **Async handlers** (SQS, EventBridge): Return success/failure for retry logic

Error messages MUST be actionable for consumers (not internal stack traces). Timeouts MUST be handled gracefully with partial results when possible.

**Rationale**: Inconsistent responses break client integrations and complicate debugging. Lambda consumers (API Gateway, EventBridge, SQS) rely on predictable success/failure patterns for retries and error handling.

## Performance & Reliability Standards

### Latency Requirements

- **Synchronous handlers** (API Gateway): p95 latency < 1000ms cold start, < 200ms warm
- **Asynchronous handlers** (SQS, EventBridge): p95 latency < 5000ms per message
- **Bedrock agent invocations**: Timeout 30s, retry with exponential backoff (3 attempts max)

Functions exceeding these thresholds MUST be profiled and optimized before production deployment.

### Concurrency & Throttling

- Each Lambda MUST define reserved concurrency OR use account-level limits explicitly
- Handlers MUST implement retry logic for throttling errors from AWS services (boto3 built-in retry + custom exponential backoff)
- DLQ (Dead Letter Queue) MUST be configured for all asynchronous event sources

### Resource Constraints

- **Memory**: Start with 512MB, tune based on CloudWatch metrics (monitor max used)
- **Timeout**: Set to 3x expected p95 latency (e.g., 10s for 3s p95), never exceed 15 minutes
- **Deployment package**: Keep under 10MB uncompressed (use Lambda layers for large dependencies)
- **Cold start optimization**: Minimize import statements, lazy-load heavy libraries, use connection pooling

### Reliability Patterns

All handlers MUST implement:
- **Idempotency**: Safe to retry (use request IDs, conditional writes to avoid duplicates)
- **Graceful degradation**: Return partial results on non-critical failures
- **Circuit breaker**: Back off on repeated downstream failures (prevent cascading failures)
- **Input validation**: Reject malformed events early with clear error messages

## Development Workflow

### Adding a New Lambda Function

1. **Specification**: Create feature spec in specs/ following /speckit.specify workflow
2. **Design**: Run /speckit.plan to generate implementation plan with handler interface
3. **Tests First**: Write unit tests in tests/test_<handler_name>.py, create test events in tests/events/
4. **SAM Template**: Add Lambda function resource to template.yaml (IaC principle)
5. **Implementation**: Write handler in src/<handler_name>.py until tests pass
6. **Coverage Check**: Run pytest --cov=src --cov-report=term - MUST show ≥80%
7. **Local Testing**: sam local invoke with test events
8. **Deploy to Dev**: sam build && sam deploy --config-env dev
9. **Integration Testing**: Validate with live AWS resources in dev environment
10. **Documentation**: Update README.md with function purpose, triggers, resources, monitoring

### Code Review Requirements

Pull requests MUST pass:
- ✅ All pytest tests pass
- ✅ Code coverage ≥80%
- ✅ sam validate --lint passes (SAM template validation)
- ✅ No secrets or credentials in code (use Secrets Manager/Parameter Store)
- ✅ README.md updated with new function documentation
- ✅ Constitution compliance verified (reviewers check these principles)

### Deployment Gates

- **Dev**: Auto-deploy on merge to main (requires manual confirmation per samconfig.toml)
- **Staging**: Auto-deploy on dev success, skip confirmation
- **Prod**: Manual approval required, deploy during maintenance window, monitor for 1 hour post-deploy

## Governance

This constitution supersedes all informal practices and preferences. Amendments require:
1. Documented proposal with rationale
2. Team review and approval
3. Migration plan for existing code (if backward incompatible)
4. Version bump per semantic versioning rules

All pull requests and code reviews MUST verify compliance with these principles. Complexity (e.g., violating function-first by creating shared libraries, or skipping tests due to deadlines) MUST be justified in writing with:
- Why the principle cannot be followed
- What simpler alternatives were rejected and why
- Plan to refactor toward compliance

**Version**: 1.0.0 | **Ratified**: 2025-11-11 | **Last Amended**: 2025-11-11
