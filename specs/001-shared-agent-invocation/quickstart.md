# Quickstart Guide

> **Note**: For current development workflow, see:
> - [README.md](../../../README.md) - Architecture overview
> - [DEPLOYMENT.md](../../../DEPLOYMENT.md) - Deployment instructions
> - [LOCAL_TESTING.md](../../../LOCAL_TESTING.md) - Testing guide

## Prerequisites

Before starting implementation, ensure you have:

✅ Python 3.13+ installed
✅ uv package manager installed ([installation guide](https://docs.astral.sh/uv/))
✅ AWS CLI configured with credentials
✅ AWS SAM CLI installed (`uv tool install aws-sam-cli`)
✅ Access to Amazon Bedrock with at least one AgentCore agent created
✅ Read the project constitution (`.specify/memory/constitution.md`)
✅ Read the feature spec (`specs/001-shared-agent-invocation/spec.md`)

## Step 1: Create Test Events (5 min)

**Following Constitution III: Test-First Development**

Create test event files in `tests/events/`:

### Direct Invocation Event

Create `tests/events/agentcore-invocation-direct.json`:

```json
{
  "agentId": "TESTABC123",
  "agentAliasId": "TSTALIASID",
  "sessionId": "123e4567-e89b-12d3-a456-426614174000",
  "inputText": "What is the weather in San Francisco?"
}
```

### API Gateway Event

Create `tests/events/agentcore-invocation-api-gateway.json`:

```json
{
  "body": "{\"agentId\":\"TESTABC123\",\"agentAliasId\":\"TSTALIASID\",\"inputText\":\"What is the weather in San Francisco?\"}",
  "headers": {
    "Content-Type": "application/json"
  },
  "requestContext": {
    "requestId": "test-api-gateway-request-id",
    "httpMethod": "POST"
  },
  "isBase64Encoded": false
}
```

### Invalid Input Event (for validation tests)

Create `tests/events/agentcore-invocation-invalid.json`:

```json
{
  "agentId": "invalid-id",
  "agentAliasId": "TSTALIASID",
  "inputText": ""
}
```

---

## Step 2: Write Unit Tests FIRST (30 min)

**Following Constitution III: Test-First Development - Tests MUST fail before implementation**

Create `tests/test_agentcore_invocation_handler.py`:

```python
import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import will fail initially - this is expected (test-first)
# from src.agentcore_invocation_handler import lambda_handler, parse_event, validate_request, invoke_agent

class TestEventParsing:
    """Test event parsing for different trigger sources"""

    def test_parse_direct_invocation(self):
        """Direct invocation event should pass through unchanged"""
        event = {
            "agentId": "TESTABC123",
            "agentAliasId": "TSTALIASID",
            "inputText": "Test input"
        }
        # from src.agentcore_invocation_handler import parse_event
        # result = parse_event(event)
        # assert result == event
        pytest.skip("Handler not implemented yet - write this test, verify it fails, then implement")

    def test_parse_api_gateway_event(self):
        """API Gateway event should extract body as JSON"""
        event = {
            "body": json.dumps({
                "agentId": "TESTABC123",
                "inputText": "Test"
            }),
            "requestContext": {}
        }
        pytest.skip("Handler not implemented yet")

    def test_parse_eventbridge_event(self):
        """EventBridge event should extract detail field"""
        event = {
            "detail": {
                "agentId": "TESTABC123",
                "inputText": "Test"
            }
        }
        pytest.skip("Handler not implemented yet")


class TestInputValidation:
    """Test input validation rules"""

    def test_valid_agent_id(self):
        """Valid agent ID (10 uppercase alphanumeric) should pass"""
        pytest.skip("Write validation test - should FAIL before implementation")

    def test_invalid_agent_id_format(self):
        """Invalid agent ID format should return ValidationError"""
        pytest.skip("Write validation test")

    def test_valid_agent_alias_id(self):
        """Valid alias ID should pass"""
        pytest.skip("Write validation test")

    def test_special_alias_ids(self):
        """TSTALIASID and DRAFT should be accepted"""
        pytest.skip("Write validation test")

    def test_valid_session_id(self):
        """Valid UUID v4 session ID should pass"""
        pytest.skip("Write validation test")

    def test_invalid_session_id(self):
        """Invalid session ID format should return ValidationError"""
        pytest.skip("Write validation test")

    def test_empty_input_text(self):
        """Empty input text should return ValidationError"""
        pytest.skip("Write validation test")

    def test_input_text_exceeds_max_size(self):
        """Input text >25KB should return ValidationError"""
        pytest.skip("Write validation test")


class TestLambdaHandler:
    """Test main Lambda handler function"""

    @patch('boto3.client')
    def test_successful_invocation(self, mock_boto_client):
        """Successful agent invocation should return structured response"""
        # Mock Bedrock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        # Mock EventStream response from Bedrock
        mock_client.invoke_agent.return_value = {
            'completion': [
                {'chunk': {'bytes': b'The weather in'}},
                {'chunk': {'bytes': b' San Francisco is'}},
                {'chunk': {'bytes': b' 68F and sunny.'}},
            ],
            'sessionId': '123e4567-e89b-12d3-a456-426614174000'
        }

        event = {
            "agentId": "TESTABC123",
            "agentAliasId": "TSTALIASID",
            "inputText": "What is the weather?"
        }

        context = Mock()
        context.request_id = "test-request-id"

        pytest.skip("Write test - should FAIL until handler implemented")
        # Uncomment after creating handler:
        # from src.agentcore_invocation_handler import lambda_handler
        # response = lambda_handler(event, context)
        #
        # assert response['status'] == 'success'
        # assert 'data' in response
        # assert response['data']['output'] == 'The weather in San Francisco is 68F and sunny.'
        # assert response['data']['sessionId'] == '123e4567-e89b-12d3-a456-426614174000'
        # assert 'metadata' in response
        # assert response['metadata']['requestId'] == 'test-request-id'

    @patch('boto3.client')
    def test_validation_error_response(self, mock_boto_client):
        """Invalid input should return ValidationError without calling Bedrock"""
        event = {
            "agentId": "invalid",  # Invalid format
            "agentAliasId": "TSTALIASID",
            "inputText": "Test"
        }

        context = Mock()
        context.request_id = "test-request-id"

        pytest.skip("Write test - should FAIL until handler implemented")
        # Uncomment after creating handler:
        # from src.agentcore_invocation_handler import lambda_handler
        # response = lambda_handler(event, context)
        #
        # assert response['status'] == 'error'
        # assert response['errorType'] == 'ValidationError'
        # assert response['retryable'] == False
        # mock_boto_client.assert_not_called()  # Should not call Bedrock

    @patch('boto3.client')
    def test_agent_not_found_error(self, mock_boto_client):
        """Agent not found should return AgentNotFound error"""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        # Mock Bedrock ResourceNotFoundException
        mock_client.invoke_agent.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Agent not found'
                }
            },
            operation_name='invoke_agent'
        )

        event = {
            "agentId": "TESTABC123",
            "agentAliasId": "TSTALIASID",
            "inputText": "Test"
        }

        context = Mock()
        context.request_id = "test-request-id"

        pytest.skip("Write test - should FAIL until handler implemented")

    @patch('boto3.client')
    def test_throttling_with_retry(self, mock_boto_client):
        """Throttling error should trigger retry with exponential backoff"""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        # First call: throttling, second call: success
        mock_client.invoke_agent.side_effect = [
            ClientError(
                error_response={'Error': {'Code': 'ThrottlingException'}},
                operation_name='invoke_agent'
            ),
            {
                'completion': [
                    {'chunk': {'bytes': b'Success after retry'}},
                ],
                'sessionId': 'session-id'
            }
        ]

        event = {
            "agentId": "TESTABC123",
            "agentAliasId": "TSTALIASID",
            "inputText": "Test"
        }

        context = Mock()
        context.request_id = "test-request-id"

        pytest.skip("Write test - should FAIL until handler implemented")


class TestStructuredLogging:
    """Test structured logging requirements (Constitution V)"""

    @patch('boto3.client')
    @patch('logging.Logger.info')
    def test_logs_include_required_fields(self, mock_logger, mock_boto_client):
        """Logs should include requestId, agentId, executionTime, status"""
        pytest.skip("Write test to verify structured logging")


class TestObservability:
    """Test observability requirements"""

    def test_response_includes_metadata(self):
        """All responses should include metadata with requestId, timestamp"""
        pytest.skip("Write test to verify metadata in response")

    def test_execution_time_tracked(self):
        """Response metadata should include executionTimeMs"""
        pytest.skip("Write test to verify execution time tracking")


# Run tests to verify they FAIL
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**✅ Checkpoint**: Run `uv run pytest tests/test_agentcore_invocation_handler.py -v`

**Expected Result**: Tests should be SKIPPED (pytest.skip) or FAIL (import error). This is CORRECT per test-first development.

---

## Step 3: Update Dependencies (5 min)

Add boto3 to Lambda runtime dependencies:

Edit `src/requirements.txt`:

```txt
# Existing dependencies...

# Bedrock Agent Runtime support
boto3>=1.34.0
botocore>=1.34.0
```

**Why**: Bedrock Agent Runtime API requires recent boto3 version (≥1.34.0)

Sync dev environment:

```bash
uv sync --extra dev
```

---

## Step 4: Implement Handler (60 min)

**Following Constitution III: Implement to make tests pass**

Create `src/agentcore_invocation_handler.py`:

```python
"""
Amazon Bedrock AgentCore Invocation Lambda Handler

Invokes AgentCore agents with structured input/output, error handling, and observability.
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure logging (Constitution V: Observability by Default)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock client configuration with retry
BEDROCK_CONFIG = Config(
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# Initialize Bedrock AgentCore client (outside handler for connection pooling)
bedrock_client = boto3.client('bedrock-agentcore', config=BEDROCK_CONFIG)


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda handler for AgentCore invocation.

    Args:
        event: Lambda event (varies by trigger source)
        context: Lambda context with request_id

    Returns:
        dict: AgentInvocationResponse or AgentInvocationError
    """
    start_time = time.time()
    request_id = context.request_id

    try:
        # Log invocation start
        log_structured('INFO', 'Agent invocation started', requestId=request_id)

        # Parse event based on trigger source
        parsed_event = parse_event(event)

        # Validate request parameters
        validation_error = validate_request(parsed_event)
        if validation_error:
            log_structured('WARN', 'Validation failed', requestId=request_id, error=validation_error)
            return build_error_response('ValidationError', validation_error, request_id, False)

        # Extract parameters
        agent_id = parsed_event['agentId']
        agent_alias_id = parsed_event['agentAliasId']
        session_id = parsed_event.get('sessionId')
        input_text = parsed_event['inputText']
        timeout = parsed_event.get('timeout', 30)
        max_retries = parsed_event.get('maxRetries', 3)

        # Invoke agent with retry logic
        response_data = invoke_agent_with_retry(
            agent_id, agent_alias_id, session_id, input_text, max_retries
        )

        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)

        # Build success response
        response = {
            'status': 'success',
            'data': response_data,
            'metadata': {
                'requestId': request_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'executionTimeMs': execution_time_ms,
                'agentId': agent_id
            }
        }

        log_structured('INFO', 'Agent invocation succeeded',
                       requestId=request_id,
                       agentId=agent_id,
                       executionTimeMs=execution_time_ms)

        return response

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        # Map AWS errors to error types
        if error_code == 'ResourceNotFoundException':
            error_type = 'AgentNotFound'
            retryable = False
        elif error_code in ['ThrottlingException', 'ServiceQuotaExceededException']:
            error_type = 'ThrottlingError'
            retryable = True
        elif error_code == 'InternalServerException':
            error_type = 'InternalError'
            retryable = True
        else:
            error_type = 'UnknownError'
            retryable = False

        log_structured('ERROR', 'Agent invocation failed',
                       requestId=request_id,
                       errorType=error_type,
                       errorCode=error_code,
                       errorMessage=error_message)

        return build_error_response(error_type, error_message, request_id, retryable, error_code)

    except Exception as e:
        log_structured('ERROR', 'Unexpected error',
                       requestId=request_id,
                       error=str(e),
                       stackTrace=str(e))

        return build_error_response('InternalError', 'Unexpected error occurred', request_id, False)


def parse_event(event: dict) -> dict:
    """Parse event from different trigger sources"""
    # TODO: Implement event parsing
    raise NotImplementedError("Implement event parsing")


def validate_request(request: dict) -> Optional[str]:
    """Validate request parameters, return error message if invalid"""
    # TODO: Implement validation
    raise NotImplementedError("Implement validation")


def invoke_agent_with_retry(agent_id, agent_alias_id, session_id, input_text, max_retries):
    """Invoke agent with exponential backoff retry"""
    # TODO: Implement agent invocation with retry
    raise NotImplementedError("Implement agent invocation")


def build_error_response(error_type, error_message, request_id, retryable, error_code=None):
    """Build standardized error response"""
    # TODO: Implement error response builder
    raise NotImplementedError("Implement error response builder")


def log_structured(level: str, message: str, **kwargs):
    """Log structured JSON (Constitution V: Observability)"""
    # TODO: Implement structured logging
    raise NotImplementedError("Implement structured logging")
```

**✅ Checkpoint**: Now implement each `NotImplementedError` function one at a time, running tests after each to verify progress.

**Implementation Order** (follow tests):
1. `parse_event()` - Make event parsing tests pass
2. `validate_request()` - Make validation tests pass
3. `log_structured()` - Make logging tests pass
4. `build_error_response()` - Make error response tests pass
5. `invoke_agent_with_retry()` - Make agent invocation tests pass
6. Complete `lambda_handler()` - Make integration tests pass

---

## Step 5: Add SAM Template Resource (10 min)

**Following Constitution II: Infrastructure as Code (NON-NEGOTIABLE)**

Edit `template.yaml`, add new Lambda function resource after existing `SESEmailHandlerFunction`:

```yaml
# Copy from specs/001-shared-agent-invocation/contracts/sam-template-resource.yaml
AgentCoreInvocationFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub agentcore-invocation-handler-${Environment}
    # ... (copy full resource from contract file)
```

Add outputs at end of `template.yaml`:

```yaml
Outputs:
  # ... existing outputs ...

  AgentCoreInvocationFunctionArn:
    Description: ARN of the AgentCore Invocation Lambda function
    Value: !GetAtt AgentCoreInvocationFunction.Arn

  AgentCoreInvocationFunctionName:
    Description: Name of the AgentCore Invocation Lambda function
    Value: !Ref AgentCoreInvocationFunction
```

Validate template:

```bash
uv tool run sam validate --lint
```

**Expected**: No errors

---

## Step 6: Run Tests (5 min)

**Following Constitution IV: 80% Coverage Requirement**

Run full test suite:

```bash
uv run pytest tests/test_agentcore_invocation_handler.py -v
```

**Expected**: All tests PASS (green)

Check coverage:

```bash
uv run pytest tests/ --cov=src --cov-report=term --cov-report=html
```

**Expected**: ≥80% coverage for `agentcore_invocation_handler.py`

View detailed coverage:

```bash
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

---

## Step 7: Local Testing with SAM (10 min)

Build Lambda package:

```bash
uv tool run sam build
```

Test with direct invocation event:

```bash
uv tool run sam local invoke AgentCoreInvocationFunction \
  -e tests/events/agentcore-invocation-direct.json
```

**Note**: This will attempt to call real Bedrock API. Replace `TESTABC123` with your actual agent ID for testing.

---

## Step 8: Deploy to Dev (10 min)

**Following Constitution II: Infrastructure as Code**

Deploy to dev environment:

```bash
uv tool run sam build
uv tool run sam deploy --config-env dev
```

Verify deployment:

```bash
aws cloudformation describe-stacks \
  --stack-name bedrock-agentcore-lambda-dev \
  --query 'Stacks[0].Outputs'
```

**Expected**: See `AgentCoreInvocationFunctionArn` in outputs

---

## Step 9: Integration Testing (15 min)

Test with real agent in dev environment:

```bash
aws lambda invoke \
  --function-name agentcore-invocation-handler-dev \
  --payload file://tests/events/agentcore-invocation-direct.json \
  response.json

cat response.json | jq
```

**Verify**:
- Response status is `"success"`
- `data.output` contains agent response
- `metadata.requestId` is present
- `metadata.executionTimeMs` is reasonable (<30000)

Test error scenarios:

```bash
# Invalid agent ID
aws lambda invoke \
  --function-name agentcore-invocation-handler-dev \
  --payload file://tests/events/agentcore-invocation-invalid.json \
  error-response.json

cat error-response.json | jq
```

**Verify**:
- Response status is `"error"`
- `errorType` is `"ValidationError"`
- `retryable` is `false`

---

## Step 10: Monitor Observability (10 min)

**Following Constitution V: Observability by Default**

### CloudWatch Logs

```bash
uv tool run sam logs -n AgentCoreInvocationFunction \
  --stack-name bedrock-agentcore-lambda-dev \
  --tail
```

**Verify**: Structured JSON logs with `requestId`, `agentId`, `executionTimeMs`

### X-Ray Traces

Open AWS X-Ray console:

```bash
open "https://console.aws.amazon.com/xray/home?region=us-west-2#/service-map"
```

**Verify**: Trace shows Lambda → Bedrock agent call with timing

### CloudWatch Metrics

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=agentcore-invocation-handler-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum
```

---

## Step 11: Update README (5 min)

Add new function documentation to `README.md`:

```markdown
### AgentCore Invocation Handler

Invokes Amazon Bedrock AgentCore agents with structured input/output.

**Resources:**
- Lambda: `agentcore-invocation-handler-{env}`
- No additional AWS resources (calls Bedrock API directly)

**Usage:**

\`\`\`bash
aws lambda invoke \\
  --function-name agentcore-invocation-handler-dev \\
  --payload '{"agentId":"YOUR_AGENT_ID","agentAliasId":"TSTALIASID","inputText":"Hello"}' \\
  response.json
\`\`\`

**Monitoring:**

\`\`\`bash
# View logs
uv tool run sam logs -n AgentCoreInvocationFunction --stack-name bedrock-agentcore-lambda-dev --tail

# View traces in X-Ray console
\`\`\`

See `specs/001-shared-agent-invocation/` for detailed documentation.
```

---

## Step 12: Create Pull Request

Following Constitution's Code Review Requirements:

```bash
# Verify all checks pass
uv run pytest tests/ -v                    # ✅ All tests pass
uv run pytest tests/ --cov=src             # ✅ Coverage ≥80%
uv tool run sam validate --lint            # ✅ SAM template valid
grep -r "AKIA\|AWS_SECRET" src/            # ✅ No credentials in code
git diff README.md                         # ✅ README updated
```

Create commit:

```bash
git add src/agentcore_invocation_handler.py
git add tests/test_agentcore_invocation_handler.py
git add tests/events/agentcore-invocation-*.json
git add template.yaml
git add README.md
git add src/requirements.txt

git commit -m "feat: add AgentCore invocation Lambda handler

- Implement Lambda handler for Bedrock AgentCore agent invocation
- Support multiple event sources (API Gateway, EventBridge, direct)
- Add input validation, retry logic, structured logging
- Achieve 85% test coverage (exceeds 80% requirement)
- Add SAM template resource with IAM permissions
- Update README with usage documentation

Closes #1 (001-shared-agent-invocation)
"
```

Push and create PR:

```bash
git push origin 001-shared-agent-invocation
```

---

## Troubleshooting

### Tests failing with import errors

**Cause**: Handler file not created yet
**Fix**: This is expected for test-first development. Implement handler to fix.

### SAM build fails

**Cause**: Invalid syntax in template.yaml
**Fix**: Run `uv tool run sam validate --lint` for details

### Bedrock permission denied in dev

**Cause**: Lambda execution role missing `bedrock-agentcore:InvokeAgentRuntime`
**Fix**: Verify IAM policy in SAM template includes Bedrock AgentCore permissions (uses bedrock-agentcore client)

### Coverage below 80%

**Cause**: Missing tests for error paths
**Fix**: Add tests for all error scenarios (validation, throttling, timeout)

---

## Success Criteria

✅ All unit tests pass
✅ Test coverage ≥80%
✅ SAM template validates without errors
✅ Function deploys successfully to dev
✅ Integration test with real agent succeeds
✅ Structured logs visible in CloudWatch
✅ X-Ray traces show Bedrock API calls
✅ README documentation updated
✅ Constitution compliance verified

---

## Next Steps

After feature is complete:

1. Deploy to staging: `uv tool run sam deploy --config-env staging`
2. Run load tests: Verify 100 concurrent invocations
3. Deploy to prod: `uv tool run sam deploy --config-env prod`
4. Monitor for 1 hour post-prod deployment
5. Document lessons learned in feature retrospective

---

## Resources

- Feature Spec: `specs/001-shared-agent-invocation/spec.md`
- Research: `specs/001-shared-agent-invocation/research.md`
- Data Model: `specs/001-shared-agent-invocation/data-model.md`
- Contracts: `specs/001-shared-agent-invocation/contracts/`
- Bedrock Agent Runtime API: [AWS Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-api.html)
- Project Constitution: `.specify/memory/constitution.md`
