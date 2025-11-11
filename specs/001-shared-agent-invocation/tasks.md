# Tasks: Shared AgentCore Invocation Module

**Input**: Design documents from `/specs/001-shared-agent-invocation/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Tests are NOT explicitly requested in the specification, so test tasks are NOT included per speckit guidelines.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and three-layer architecture setup

- [ ] T001 Create `src/integrations/` directory for AWS service integrations
- [ ] T002 Create `src/integrations/__init__.py` to make integrations a package
- [ ] T003 Create `src/services/` directory for utility functions
- [ ] T004 Create `src/services/__init__.py` to make services a package
- [ ] T005 Create `tests/integrations/` directory for AWS integration tests
- [ ] T006 Create `tests/services/` directory for service utility tests
- [ ] T007 Update `src/requirements.txt` to add boto3>=1.34.0 and botocore>=1.34.0

**Checkpoint**: Directory structure ready for three-layer architecture (handlers, services, integrations)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core exception classes and configuration that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Create custom exception classes in `src/integrations/agentcore_invocation.py`: ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException
- [ ] T009 Implement environment variable reading for AGENT_RUNTIME_ARN in `src/integrations/agentcore_invocation.py` (at module import time, raise ConfigurationError if missing)
- [ ] T010 Initialize boto3 bedrock-agentcore client with retry config in `src/integrations/agentcore_invocation.py` (module-level, thread-safe)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Shared Module Integration (Priority: P1) 🎯 MVP

**Goal**: Provide a reusable `invoke_agent()` function that Lambda handlers can import and use to invoke Bedrock AgentCore agents

**Independent Test**: Import the module in the existing SQS email handler, call `invoke_agent()` with a test prompt, verify the agent response is returned

### Implementation for User Story 1

- [ ] T011 [US1] Implement `invoke_agent(prompt: str, session_id: Optional[str] = None, **kwargs) -> str` function signature in `src/integrations/agentcore_invocation.py`
- [ ] T012 [US1] Implement session ID generation logic in `src/integrations/agentcore_invocation.py` (if None, generate 33+ char UUID4 with "session-" prefix)
- [ ] T013 [US1] Implement Bedrock API call to `client.invoke_agent_runtime()` in `src/integrations/agentcore_invocation.py` with agentRuntimeArn, runtimeSessionId, payload parameters
- [ ] T014 [US1] Implement payload formatting as JSON string `{"prompt": "text"}` in `src/integrations/agentcore_invocation.py`
- [ ] T015 [US1] Implement EventStream response handling with `.read()` and JSON parsing in `src/integrations/agentcore_invocation.py`
- [ ] T016 [US1] Implement response aggregation to collect all chunks and return complete agent output as string in `src/integrations/agentcore_invocation.py`
- [ ] T017 [US1] Add module-level docstring and function docstring with usage example in `src/integrations/agentcore_invocation.py`

**Checkpoint**: At this point, User Story 1 should be fully functional - handlers can import and invoke agents

---

## Phase 4: User Story 2 - Environment-Based Configuration (Priority: P1)

**Goal**: Enable configuration of agent ARN via environment variables, supporting multi-environment deployments without code changes

**Independent Test**: Deploy with AGENT_RUNTIME_ARN set to a test agent in dev environment, verify invocations use that agent

### Implementation for User Story 2

- [ ] T018 [US2] Update SAM template `template.yaml` to add AGENT_RUNTIME_ARN environment variable to all Lambda functions (under Globals or per function)
- [ ] T019 [US2] Update `samconfig.toml` to include AGENT_RUNTIME_ARN parameter mapping for dev/staging/prod environments
- [ ] T020 [US2] Add validation in `src/integrations/agentcore_invocation.py` module initialization to ensure AGENT_RUNTIME_ARN format is valid (starts with "arn:aws:bedrock-agentcore:")
- [ ] T021 [US2] Add structured logging in `src/integrations/agentcore_invocation.py` to log agent ARN being used at module initialization (INFO level)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - handlers can invoke agents with environment-specific configuration

---

## Phase 5: User Story 3 - Error Handling for Callers (Priority: P2)

**Goal**: Provide clear error messages and domain-specific exceptions so handlers can implement appropriate error recovery strategies

**Independent Test**: Call `invoke_agent()` with invalid prompt or during Bedrock service issues, verify appropriate exception is raised with actionable error message

### Implementation for User Story 3

- [ ] T022 [P] [US3] Implement prompt validation in `src/integrations/agentcore_invocation.py` (non-empty string check before Bedrock call, raise ValidationException if invalid)
- [ ] T023 [P] [US3] Implement session_id validation in `src/integrations/agentcore_invocation.py` (None or UUID4 format, raise ValidationException if invalid)
- [ ] T024 [US3] Implement error mapping for botocore ClientError exceptions in `src/integrations/agentcore_invocation.py` (map ResourceNotFoundException → AgentNotFoundException, ThrottlingException → ThrottlingException, etc.)
- [ ] T025 [US3] Implement retry logic with exponential backoff in `src/integrations/agentcore_invocation.py` (up to 3 attempts for transient errors: ThrottlingException, InternalServerException)
- [ ] T026 [US3] Add structured logging for error scenarios in `src/integrations/agentcore_invocation.py` (log error type, agent ARN, retry attempts at ERROR level)
- [ ] T027 [US3] Ensure exception messages include actionable information in `src/integrations/agentcore_invocation.py` (agent ARN, error code, retry advice)

**Checkpoint**: All core agent invocation functionality complete - error handling is production-ready

---

## Phase 6: Services Layer Implementation

**Goal**: Implement reusable utility functions for email processing and S3 operations that handlers will use

**Independent Test**: Import service functions in SQS email handler, verify email body extraction and S3 operations work correctly

### Implementation for Services Layer

- [ ] T028 [P] Create `src/services/email.py` with `extract_email_body(email_content: str) -> str` function for extracting body text from email
- [ ] T029 [P] Create `src/services/email.py` with `parse_email_headers(email_content: str) -> dict` function for parsing email headers
- [ ] T030 [P] Create `src/services/s3.py` with `fetch_email_from_s3(bucket: str, key: str) -> str` function using boto3 S3 client
- [ ] T031 [P] Create `src/services/s3.py` with `upload_processed_result(bucket: str, key: str, content: str)` function for uploading results to S3
- [ ] T032 [P] Add error handling and logging to all service functions in `src/services/email.py` and `src/services/s3.py`
- [ ] T033 [P] Add function docstrings with usage examples to all service functions in `src/services/email.py` and `src/services/s3.py`

**Checkpoint**: Services layer complete - handlers can use email and S3 utilities

---

## Phase 7: User Story 4 - SQS Integration Testing (Priority: P2)

**Goal**: Enable local and integration testing of agent invocations from SQS-triggered handlers

**Independent Test**: Run `sam local invoke` with an SQS test event, verify the handler processes the SQS message, invokes the agent, and returns a successful response

### Implementation for User Story 4

- [ ] T034 [US4] Create `tests/events/sqs-email-with-agent-invocation.json` test event based on SES notification format with email body suitable for agent summarization
- [ ] T035 [US4] Update existing SQS email handler `src/sqs_email_handler.py` to import services: `from services import email, s3`
- [ ] T036 [US4] Update existing SQS email handler `src/sqs_email_handler.py` to import integrations: `from integrations import agentcore_invocation`
- [ ] T037 [US4] Refactor handler logic in `src/sqs_email_handler.py` to use clean three-layer pattern: delegate S3 operations to `s3.fetch_email_from_s3()`, email parsing to `email.extract_email_body()`, agent invocation to `agentcore_invocation.invoke_agent()`
- [ ] T038 [US4] Add agent invocation call in `src/sqs_email_handler.py` using prompt format: `f"Summarize this email: {body}"` with session_id=None
- [ ] T039 [US4] Add error handling in `src/sqs_email_handler.py` to catch agent invocation exceptions (ConfigurationError, AgentNotFoundException, ThrottlingException, ValidationException) and return appropriate responses
- [ ] T040 [US4] Update handler response structure in `src/sqs_email_handler.py` to include agent summary in output
- [ ] T041 [US4] Add structured logging to handler in `src/sqs_email_handler.py` for agent invocation events (prompt length, response length, execution time)

**Checkpoint**: All user stories complete - SQS handler uses clean three-layer architecture with agent invocation

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and production readiness improvements

- [ ] T042 [P] Create example handler code snippet in `specs/001-shared-agent-invocation/contracts/lambda-handler-interface.md` showing clean usage pattern
- [ ] T043 [P] Update project README.md with three-layer architecture documentation (handlers → services → integrations)
- [ ] T044 Validate quickstart.md instructions by following them step-by-step in a clean environment
- [ ] T045 Run `sam build` to verify all modules are packaged correctly
- [ ] T046 Run `sam validate --lint` to ensure SAM template is valid
- [ ] T047 Verify module has no side effects on import except environment variable reading (check for print statements, I/O operations)
- [ ] T048 Review all structured logging statements to ensure they follow JSON format and include required fields (requestId, agentId, executionTime)
- [ ] T049 [P] Update CLAUDE.md with completed feature information (architecture confirmed, modules deployed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational (Phase 2) - No dependencies on other stories
  - User Story 2 (P1): Depends on User Story 1 completion (extends configuration)
  - User Story 3 (P2): Depends on User Story 1 completion (adds error handling to core function)
- **Services Layer (Phase 6)**: Can run in parallel with User Stories 3-4 (different files)
- **User Story 4 (Phase 7)**: Depends on User Story 1 and Services Layer (Phase 6) completion
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Core `invoke_agent()` function - BLOCKS US2, US3, US4
- **User Story 2 (P1)**: Environment configuration - extends US1, no blocking
- **User Story 3 (P2)**: Error handling - enhances US1, no blocking
- **User Story 4 (P2)**: SQS integration - requires US1 + Services Layer

### Within Each User Story

- Module structure before implementation
- Core function before enhancements
- Error handling after core functionality
- Logging throughout all stages

### Parallel Opportunities

**Phase 1 (Setup)**: All tasks T001-T007 can run in parallel (creating directories and files)

**Phase 2 (Foundational)**: Tasks T008-T010 are sequential (exceptions → config → client)

**Phase 3 (User Story 1)**: Tasks T011-T017 are mostly sequential (function signature → session ID → API call → response handling)

**Phase 5 (User Story 3)**: Tasks T022-T023 can run in parallel (different validation functions)

**Phase 6 (Services Layer)**: All tasks T028-T033 can run in parallel (different files: email.py vs s3.py)

**Phase 8 (Polish)**: Tasks T042-T043, T049 can run in parallel (different documentation files)

---

## Parallel Example: Services Layer (Phase 6)

```bash
# Launch all service implementations in parallel:
Task: "Create src/services/email.py with extract_email_body() function"
Task: "Create src/services/email.py with parse_email_headers() function"
Task: "Create src/services/s3.py with fetch_email_from_s3() function"
Task: "Create src/services/s3.py with upload_processed_result() function"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T010) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T011-T017)
4. **STOP and VALIDATE**: Test User Story 1 independently by importing in a test handler
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational (Phases 1-2) → Foundation ready
2. Add User Story 1 (Phase 3) → Test independently → Core functionality works! 🎯 MVP
3. Add User Story 2 (Phase 4) → Test with different environments → Multi-env support works!
4. Add Services Layer (Phase 6) → Test service functions → Utilities ready!
5. Add User Story 3 (Phase 5) → Test error scenarios → Production-ready error handling!
6. Add User Story 4 (Phase 7) → Test SQS integration → Complete clean handler pattern!
7. Polish (Phase 8) → Documentation and validation complete

Each increment adds value without breaking previous functionality.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup (Phase 1) together (quick - ~5 min)
2. Team completes Foundational (Phase 2) together (critical - ~15 min)
3. Once Foundational is done:
   - **Developer A**: User Story 1 (Phase 3) - CORE (blocks others)
4. Once User Story 1 is done:
   - **Developer A**: User Story 2 (Phase 4) - Configuration
   - **Developer B**: Services Layer (Phase 6) - Utilities (parallel)
5. Once User Story 1 and Services are done:
   - **Developer A**: User Story 3 (Phase 5) - Error handling
   - **Developer B**: User Story 4 (Phase 7) - SQS integration
6. Both developers: Polish (Phase 8) - Documentation

---

## Task Count Summary

- **Phase 1 (Setup)**: 7 tasks
- **Phase 2 (Foundational)**: 3 tasks
- **Phase 3 (User Story 1)**: 7 tasks
- **Phase 4 (User Story 2)**: 4 tasks
- **Phase 5 (User Story 3)**: 6 tasks
- **Phase 6 (Services Layer)**: 6 tasks
- **Phase 7 (User Story 4)**: 8 tasks
- **Phase 8 (Polish)**: 8 tasks

**Total: 49 tasks**

**Tasks per User Story**:
- User Story 1 (P1): 7 tasks
- User Story 2 (P1): 4 tasks
- User Story 3 (P2): 6 tasks
- User Story 4 (P2): 8 tasks

**Parallel Opportunities**: 15 tasks marked [P] can run in parallel with other tasks in same phase

**Suggested MVP Scope**: Phases 1-3 (Setup + Foundational + User Story 1) = 17 tasks

---

## Format Validation

✅ ALL tasks follow the checklist format:
- ✅ Checkbox: `- [ ]` present on all tasks
- ✅ Task ID: Sequential (T001-T049) in execution order
- ✅ [P] marker: Used on 15 parallelizable tasks
- ✅ [Story] label: Used on all user story phase tasks (US1, US2, US3, US4)
- ✅ Description: Clear action with exact file path
- ✅ Setup phase: No story labels
- ✅ Foundational phase: No story labels
- ✅ User Story phases: All have story labels
- ✅ Polish phase: No story labels

---

## Notes

- Tests are NOT included because they were not explicitly requested in the feature specification
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Three-layer architecture: handlers (business logic) → services (utilities) → integrations (AWS APIs)
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
