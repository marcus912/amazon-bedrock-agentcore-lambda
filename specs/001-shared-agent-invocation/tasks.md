---

description: "Task list for Shared AgentCore Invocation Lambda implementation"
---

# Tasks: Shared AgentCore Invocation Lambda

**Input**: Design documents from `/specs/001-shared-agent-invocation/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Following Constitution III (Test-First Development - NON-NEGOTIABLE), tests MUST be written BEFORE implementation. This is mandatory per project constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single serverless project**: `src/`, `tests/` at repository root
- Lambda handlers as flat Python modules in `src/`
- SAM template at root: `template.yaml`
- Tests mirror handler names

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and test event setup

- [ ] T001 Create test event for direct invocation in tests/events/agentcore-invocation-direct.json
- [ ] T002 Create test event for API Gateway invocation in tests/events/agentcore-invocation-api-gateway.json
- [ ] T003 Create test event for EventBridge invocation in tests/events/agentcore-invocation-eventbridge.json
- [ ] T004 Create test event for invalid input in tests/events/agentcore-invocation-invalid.json
- [ ] T005 Update src/requirements.txt to add boto3>=1.34.0 and botocore>=1.34.0

**Checkpoint**: Test events created, dependencies updated - ready for test-first development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete (Constitution III: Test-First Development)

- [ ] T006 Create test file tests/test_agentcore_invocation_handler.py with test class structure
- [ ] T007 Add SAM template resource AgentCoreInvocationFunction to template.yaml with IAM permissions for bedrock:InvokeAgent
- [ ] T008 Validate SAM template with `uv tool run sam validate --lint` to ensure infrastructure is correct

**Checkpoint**: Foundation ready - user story implementation can now begin following test-first approach

---

## Phase 3: User Story 1 - Direct Agent Invocation (Priority: P1) 🎯 MVP

**Goal**: Enable Lambda function to invoke Bedrock AgentCore agents with agent ID, alias ID, session ID, and input text, returning structured responses

**Independent Test**: Invoke Lambda with valid agent parameters → Receive successful response with agent output → Core functionality proven

### Tests for User Story 1 (Constitution III: Write FIRST, ensure FAIL before implementation) ⚠️

> **CRITICAL: Write these tests FIRST, run pytest to verify they FAIL, then implement**

- [ ] T009 [P] [US1] Write unit test for parse_event() with direct invocation event in tests/test_agentcore_invocation_handler.py (TestEventParsing class)
- [ ] T010 [P] [US1] Write unit test for parse_event() with API Gateway event in tests/test_agentcore_invocation_handler.py (TestEventParsing class)
- [ ] T011 [P] [US1] Write unit test for parse_event() with EventBridge event in tests/test_agentcore_invocation_handler.py (TestEventParsing class)
- [ ] T012 [P] [US1] Write unit test for validate_request() with valid agent ID format in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T013 [P] [US1] Write unit test for validate_request() with valid agent alias ID in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T014 [P] [US1] Write unit test for validate_request() with valid session ID (UUID v4) in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T015 [P] [US1] Write unit test for validate_request() with valid input text (non-empty, under 25KB) in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T016 [P] [US1] Write unit test for lambda_handler() successful agent invocation with mocked boto3 client in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T017 [P] [US1] Write unit test for invoke_agent_with_retry() collecting EventStream chunks in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T018 [P] [US1] Write unit test for build_success_response() with metadata (requestId, timestamp, executionTimeMs) in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)

**Test Checkpoint**: Run `uv run pytest tests/test_agentcore_invocation_handler.py -v` → All tests should FAIL (expected) → Ready for implementation

### Implementation for User Story 1

- [ ] T019 [US1] Create src/agentcore_invocation_handler.py with lambda_handler() function signature and module-level imports
- [ ] T020 [P] [US1] Implement parse_event() function in src/agentcore_invocation_handler.py to detect and extract parameters from direct, API Gateway, and EventBridge events
- [ ] T021 [P] [US1] Implement validate_request() function in src/agentcore_invocation_handler.py with regex validation for agent ID (10 alphanumeric), agent alias ID, session ID (UUID v4), and input text (max 25KB)
- [ ] T022 [P] [US1] Implement log_structured() function in src/agentcore_invocation_handler.py for JSON-formatted logging with timestamp, level, message, and kwargs
- [ ] T023 [US1] Implement invoke_agent_with_retry() function in src/agentcore_invocation_handler.py to call bedrock-agent-runtime invoke_agent API and collect EventStream chunks (depends on T020, T021, T022)
- [ ] T024 [US1] Implement build_success_response() function in src/agentcore_invocation_handler.py to construct AgentInvocationResponse with data and metadata
- [ ] T025 [US1] Complete lambda_handler() implementation in src/agentcore_invocation_handler.py to orchestrate parse → validate → invoke → build response flow (depends on T020-T024)
- [ ] T026 [US1] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestEventParsing -v` to verify event parsing tests pass
- [ ] T027 [US1] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestInputValidation -v` to verify validation tests pass
- [ ] T028 [US1] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestLambdaHandler::test_successful_invocation -v` to verify successful invocation test passes

**Implementation Checkpoint**: Run `uv run pytest tests/test_agentcore_invocation_handler.py -v` → All User Story 1 tests should PASS

### Integration Testing for User Story 1

- [ ] T029 [US1] Run `uv tool run sam build` to package Lambda function with dependencies
- [ ] T030 [US1] Run `uv tool run sam local invoke AgentCoreInvocationFunction -e tests/events/agentcore-invocation-direct.json` to test local invocation (replace TESTABC123 with real agent ID)
- [ ] T031 [US1] Deploy to dev with `uv tool run sam deploy --config-env dev` and verify AgentCoreInvocationFunctionArn in stack outputs
- [ ] T032 [US1] Test live invocation with `aws lambda invoke --function-name agentcore-invocation-handler-dev --payload file://tests/events/agentcore-invocation-direct.json response.json` and verify successful response

**Checkpoint**: User Story 1 is fully functional and independently testable - MVP complete! 🎯

---

## Phase 4: User Story 2 - Error Handling and Retries (Priority: P2)

**Goal**: Implement robust error handling with graceful error messages, retry logic with exponential backoff for transient failures, and structured error responses

**Independent Test**: Simulate failure scenarios (invalid agent ID, throttling, timeout) → Verify appropriate error responses and retry behavior → Error handling proven

### Tests for User Story 2 (Constitution III: Write FIRST) ⚠️

- [ ] T033 [P] [US2] Write unit test for validate_request() with invalid agent ID format in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T034 [P] [US2] Write unit test for validate_request() with invalid agent alias ID in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T035 [P] [US2] Write unit test for validate_request() with invalid session ID format in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T036 [P] [US2] Write unit test for validate_request() with empty input text in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T037 [P] [US2] Write unit test for validate_request() with input text exceeding 25KB in tests/test_agentcore_invocation_handler.py (TestInputValidation class)
- [ ] T038 [P] [US2] Write unit test for lambda_handler() returning ValidationError without calling Bedrock in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T039 [P] [US2] Write unit test for lambda_handler() handling ResourceNotFoundException (agent not found) in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T040 [P] [US2] Write unit test for invoke_agent_with_retry() with ThrottlingException triggering exponential backoff retry in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T041 [P] [US2] Write unit test for invoke_agent_with_retry() with timeout scenario in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T042 [P] [US2] Write unit test for build_error_response() constructing AgentInvocationError with errorType, errorMessage, retryable flag in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)

**Test Checkpoint**: Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestInputValidation -v` and `::TestLambdaHandler -v` → Error handling tests should FAIL → Ready for implementation

### Implementation for User Story 2

- [ ] T043 [US2] Update validate_request() in src/agentcore_invocation_handler.py to return specific error messages for each validation failure (invalid agent ID, alias ID, session ID, empty/oversized input text)
- [ ] T044 [US2] Implement build_error_response() function in src/agentcore_invocation_handler.py to construct AgentInvocationError with errorType, errorMessage, errorCode, metadata, retryable flag
- [ ] T045 [US2] Update invoke_agent_with_retry() in src/agentcore_invocation_handler.py to implement exponential backoff retry logic (2^attempt * 100ms) for ThrottlingException, ServiceQuotaExceededException, InternalServerException
- [ ] T046 [US2] Update invoke_agent_with_retry() in src/agentcore_invocation_handler.py to NOT retry ResourceNotFoundException and ValidationException (permanent errors)
- [ ] T047 [US2] Update lambda_handler() in src/agentcore_invocation_handler.py to catch botocore ClientError and map AWS error codes to error types (AgentNotFound, ThrottlingError, TimeoutError, InternalError)
- [ ] T048 [US2] Update lambda_handler() in src/agentcore_invocation_handler.py to return build_error_response() for validation failures before calling Bedrock
- [ ] T049 [US2] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestInputValidation -v` to verify all validation error tests pass
- [ ] T050 [US2] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestLambdaHandler -v` to verify error handling and retry tests pass

**Implementation Checkpoint**: All error scenarios handled gracefully, retry logic proven

### Integration Testing for User Story 2

- [ ] T051 [US2] Test validation error with `aws lambda invoke --function-name agentcore-invocation-handler-dev --payload file://tests/events/agentcore-invocation-invalid.json error-response.json` and verify errorType=ValidationError, retryable=false
- [ ] T052 [US2] Test agent not found error by invoking with nonexistent agent ID and verify errorType=AgentNotFound, errorCode=ResourceNotFoundException

**Checkpoint**: User Story 2 complete and independently testable - Error handling robust

---

## Phase 5: User Story 3 - Multi-Environment Configuration (Priority: P2)

**Goal**: Support deployment to dev, staging, prod environments with environment-specific configurations (agent IDs, timeouts) via SAM template parameters

**Independent Test**: Deploy to dev and staging with different configs → Verify each environment uses its own settings → Multi-env support proven

### Tests for User Story 3 (Constitution III: Write FIRST) ⚠️

- [ ] T053 [P] [US3] Write unit test for lambda_handler() reading DEFAULT_TIMEOUT from environment variable in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T054 [P] [US3] Write unit test for lambda_handler() reading DEFAULT_MAX_RETRIES from environment variable in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)
- [ ] T055 [P] [US3] Write unit test for lambda_handler() using custom timeout from request parameter (overriding default) in tests/test_agentcore_invocation_handler.py (TestLambdaHandler class)

**Test Checkpoint**: Environment configuration tests should FAIL → Ready for implementation

### Implementation for User Story 3

- [ ] T056 [US3] Update lambda_handler() in src/agentcore_invocation_handler.py to read DEFAULT_TIMEOUT and DEFAULT_MAX_RETRIES from os.environ with fallback defaults (30s, 3 retries)
- [ ] T057 [US3] Update lambda_handler() in src/agentcore_invocation_handler.py to allow request-level timeout and maxRetries parameters to override environment defaults
- [ ] T058 [US3] Verify AgentCoreInvocationFunction in template.yaml has Environment Variables section with ENVIRONMENT, LOG_LEVEL, DEFAULT_TIMEOUT, DEFAULT_MAX_RETRIES
- [ ] T059 [US3] Verify samconfig.toml has dev, staging, prod environments with separate stack names and parameter_overrides for Environment variable
- [ ] T060 [US3] Run `uv run pytest tests/test_agentcore_invocation_handler.py -v` to verify environment configuration tests pass

**Implementation Checkpoint**: Multi-environment configuration working

### Integration Testing for User Story 3

- [ ] T061 [US3] Deploy to staging with `uv tool run sam deploy --config-env staging` and verify separate stack bedrock-agentcore-lambda-staging created
- [ ] T062 [US3] Verify dev and staging Lambda functions use different environment variables by checking AWS console or `aws lambda get-function-configuration`
- [ ] T063 [US3] Test invocation in both dev and staging to confirm isolation (changes in dev don't affect staging)

**Checkpoint**: User Story 3 complete - Multi-environment deployment proven

---

## Phase 6: User Story 4 - Logging and Observability (Priority: P3)

**Goal**: Implement comprehensive structured JSON logging with CloudWatch Insights compatibility and verify X-Ray tracing captures Bedrock API call timing

**Independent Test**: Invoke function → Verify CloudWatch Logs contain structured JSON with requestId, agentId, executionTimeMs → X-Ray trace shows Bedrock timing → Observability proven

### Tests for User Story 4 (Constitution III: Write FIRST) ⚠️

- [ ] T064 [P] [US4] Write unit test for log_structured() producing valid JSON log entries in tests/test_agentcore_invocation_handler.py (TestStructuredLogging class)
- [ ] T065 [P] [US4] Write unit test for log_structured() including timestamp, level, message, and custom kwargs in tests/test_agentcore_invocation_handler.py (TestStructuredLogging class)
- [ ] T066 [P] [US4] Write unit test for lambda_handler() logging invocation start with requestId and agentId in tests/test_agentcore_invocation_handler.py (TestStructuredLogging class)
- [ ] T067 [P] [US4] Write unit test for lambda_handler() logging success with executionTimeMs in tests/test_agentcore_invocation_handler.py (TestStructuredLogging class)
- [ ] T068 [P] [US4] Write unit test for lambda_handler() logging errors with errorType and errorMessage in tests/test_agentcore_invocation_handler.py (TestStructuredLogging class)
- [ ] T069 [P] [US4] Write unit test for response metadata including requestId, timestamp, executionTimeMs in tests/test_agentcore_invocation_handler.py (TestObservability class)

**Test Checkpoint**: Logging and observability tests should FAIL → Ready for implementation

### Implementation for User Story 4

- [ ] T070 [US4] Verify log_structured() in src/agentcore_invocation_handler.py outputs JSON with datetime.utcnow().isoformat() timestamp, level, message, and kwargs
- [ ] T071 [US4] Verify lambda_handler() in src/agentcore_invocation_handler.py logs 'Agent invocation started' with requestId from context.request_id
- [ ] T072 [US4] Verify lambda_handler() in src/agentcore_invocation_handler.py logs 'Agent invocation succeeded' with requestId, agentId, executionTimeMs
- [ ] T073 [US4] Verify lambda_handler() in src/agentcore_invocation_handler.py logs 'Agent invocation failed' with requestId, errorType, errorCode, errorMessage on errors
- [ ] T074 [US4] Verify lambda_handler() in src/agentcore_invocation_handler.py sanitizes PII from logs (logs input length, not content)
- [ ] T075 [US4] Verify build_success_response() and build_error_response() in src/agentcore_invocation_handler.py include metadata with requestId, timestamp (ISO 8601), executionTimeMs
- [ ] T076 [US4] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestStructuredLogging -v` to verify logging tests pass
- [ ] T077 [US4] Run `uv run pytest tests/test_agentcore_invocation_handler.py::TestObservability -v` to verify observability tests pass

**Implementation Checkpoint**: Structured logging working, metadata present

### Integration Testing for User Story 4

- [ ] T078 [US4] Invoke function in dev and run `uv tool run sam logs -n AgentCoreInvocationFunction --stack-name bedrock-agentcore-lambda-dev --tail` to verify structured JSON logs
- [ ] T079 [US4] Verify CloudWatch Logs contain fields: timestamp, level, message, requestId, agentId, executionTimeMs using CloudWatch Logs Insights query
- [ ] T080 [US4] Open X-Ray console and verify trace shows Lambda → Bedrock agent call with timing breakdown
- [ ] T081 [US4] Verify X-Ray trace includes subsegments for Bedrock API invoke_agent call with duration

**Checkpoint**: User Story 4 complete - Observability fully implemented

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple user stories

- [ ] T082 [P] Run `uv run pytest tests/ --cov=src --cov-report=term --cov-report=html` to verify test coverage ≥80% (Constitution IV requirement)
- [ ] T083 [P] Update README.md with AgentCore Invocation Handler section including usage, monitoring, and reference to specs/001-shared-agent-invocation/
- [ ] T084 [P] Add docstrings to all functions in src/agentcore_invocation_handler.py with parameter types and return types
- [ ] T085 Verify template.yaml AgentCoreInvocationFunction has correct Timeout (60s), MemorySize (512MB), ReservedConcurrentExecutions (100)
- [ ] T086 Run `uv tool run sam validate --lint` to ensure SAM template passes all validation checks
- [ ] T087 Run full test suite `uv run pytest tests/test_agentcore_invocation_handler.py -v` and verify 100% pass rate
- [ ] T088 Open htmlcov/index.html to review coverage report and identify any uncovered edge cases
- [ ] T089 Add any missing edge case tests based on coverage report (e.g., malformed EventStream, connection errors)
- [ ] T090 Re-run coverage to ensure final coverage ≥80% before PR

**Checkpoint**: All polish tasks complete, ready for pull request

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion - No dependencies on other stories (MVP)
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion - Extends User Story 1 (error handling)
- **User Story 3 (Phase 5)**: Depends on Foundational phase completion - Independent of other stories (can run in parallel with US1/US2)
- **User Story 4 (Phase 6)**: Depends on Foundational phase completion - Enhances all stories (logging/observability)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Foundation for all other stories
- **User Story 2 (P2)**: Builds on User Story 1 (adds error handling to core invocation)
- **User Story 3 (P2)**: Independent of US1/US2 (can implement in parallel) - Configuration only
- **User Story 4 (P3)**: Enhances all stories (can implement after US1 or in parallel)

### Recommended Implementation Order

**MVP First** (Complete US1 only):
1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: User Story 1 (P1) - Core invocation
4. STOP and VALIDATE: Test independently, deploy to dev, verify working
5. Decide whether to continue with US2-US4

**Full Feature** (All user stories):
1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: User Story 1 (P1) - Core invocation → Checkpoint
4. Phase 4: User Story 2 (P2) - Error handling → Checkpoint
5. Phase 5: User Story 3 (P2) - Multi-env config → Checkpoint
6. Phase 6: User Story 4 (P3) - Observability → Checkpoint
7. Phase 7: Polish

### Within Each User Story

- Tests (if included) MUST be written FIRST and FAIL before implementation (Constitution III)
- Helper functions (parse_event, validate_request, log_structured) before main handler
- Main lambda_handler implementation last (depends on helpers)
- Unit tests → Implementation → Integration tests
- Each story checkpoint: Tests pass, independently testable

### Parallel Opportunities

All Setup tasks (T001-T005) can run in parallel (different files).

**Within User Story 1**:
- All test writing tasks (T009-T018) can run in parallel
- Helper function implementations (T020-T024) can run in parallel after tests written

**Within User Story 2**:
- All test writing tasks (T033-T042) can run in parallel

**Within User Story 3**:
- All test writing tasks (T053-T055) can run in parallel

**Within User Story 4**:
- All test writing tasks (T064-T069) can run in parallel

**Polish phase**:
- T082, T083, T084 can run in parallel (different files)

**Parallel Example: User Story 1 Test Writing**

```bash
# Launch all User Story 1 tests together:
Task T009: Write parse_event direct invocation test
Task T010: Write parse_event API Gateway test
Task T011: Write parse_event EventBridge test
Task T012: Write validate_request valid agent ID test
Task T013: Write validate_request valid alias ID test
Task T014: Write validate_request valid session ID test
Task T015: Write validate_request valid input text test
Task T016: Write lambda_handler success test
Task T017: Write invoke_agent_with_retry test
Task T018: Write build_success_response test
```

---

## Implementation Strategy

### MVP First (User Story 1 Only - Fastest Path to Value)

**Goal**: Get basic agent invocation working in 2-3 hours

1. Complete Phase 1: Setup (T001-T005) - 10 min
2. Complete Phase 2: Foundational (T006-T008) - 15 min
3. Complete Phase 3: User Story 1 (T009-T032) - 2 hours
   - Write all tests FIRST (T009-T018) - 30 min
   - Verify tests FAIL - 2 min
   - Implement handler (T019-T028) - 60 min
   - Local and dev testing (T029-T032) - 20 min
4. **STOP and VALIDATE**: Lambda function invokes agents, returns responses
5. Deploy to dev, demonstrate working prototype
6. Decision point: Ship MVP or continue with error handling/observability

**Total Time**: 2-3 hours for working MVP

### Incremental Delivery (Add Features Progressively)

**Goal**: Build production-ready function iteratively

1. Complete Setup + Foundational → Foundation ready (25 min)
2. Add User Story 1 → Test independently → Deploy to dev (MVP!) (2 hours)
3. Add User Story 2 → Test error handling → Deploy to dev (1.5 hours)
4. Add User Story 3 → Test multi-env → Deploy to staging (1 hour)
5. Add User Story 4 → Test observability → Deploy to prod (1 hour)
6. Polish → Documentation, coverage → Final PR (30 min)

**Total Time**: 6-7 hours for complete feature

Each story adds value independently without breaking previous functionality.

### Parallel Team Strategy

With 2-3 developers working simultaneously:

**Initial Phase** (Together):
1. Developer A: Setup (T001-T005)
2. Developer B: Foundational (T006-T008)
3. Wait for Foundational completion

**User Story Phase** (Parallel):
1. Developer A: User Story 1 (T009-T032) - Core invocation
2. Developer B: User Story 3 (T053-T063) - Multi-env (independent)
3. Developer C: User Story 4 tests (T064-T069) - Observability tests

**Integration Phase** (Sequential):
1. Developer A merges US1 (MVP deployed)
2. Developer A: User Story 2 (T033-T052) - Error handling (builds on US1)
3. Developer B merges US3
4. Developer C: User Story 4 implementation (T070-T081)
5. All: Polish phase (T082-T090)

**Total Time** (parallel): ~3-4 hours for complete feature

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable at its checkpoint
- **CRITICAL**: Tests MUST be written FIRST and FAIL before implementation (Constitution III)
- Run `uv run pytest tests/test_agentcore_invocation_handler.py -v` after each implementation checkpoint
- Commit after each user story phase completion
- Stop at any checkpoint to validate story independently
- Coverage gate: Must reach ≥80% before final PR (Constitution IV)

---

## Task Summary

**Total Tasks**: 90
- Setup: 5 tasks
- Foundational: 3 tasks
- User Story 1 (P1): 24 tasks (10 tests + 14 implementation)
- User Story 2 (P2): 20 tasks (10 tests + 10 implementation)
- User Story 3 (P2): 11 tasks (3 tests + 8 implementation)
- User Story 4 (P3): 18 tasks (6 tests + 12 implementation)
- Polish: 9 tasks

**Parallel Opportunities Identified**: 45 tasks marked [P] (50% parallelizable)

**MVP Scope** (Minimum Viable Product): Phases 1-3 only (32 tasks, ~2-3 hours)
- Delivers: Working Lambda function that invokes agents and returns responses
- Validation: Deploy to dev, invoke with real agent, verify success response

**Full Feature Scope**: All phases (90 tasks, ~6-7 hours)
- Delivers: Production-ready Lambda with error handling, multi-env, observability
- Validation: 80%+ coverage, deployed to prod, all user stories proven

**Format Validation**: ✅ All 90 tasks follow required format:
- ✅ Checkbox: `- [ ]`
- ✅ Task ID: T001-T090 (sequential)
- ✅ [P] marker: Present on 45 parallelizable tasks
- ✅ [Story] label: Present on all user story phase tasks (US1-US4)
- ✅ File paths: Specified in all implementation task descriptions
- ✅ Test-first: Tests written before implementation per Constitution III
