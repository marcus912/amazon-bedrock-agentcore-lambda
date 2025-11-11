# Lambda Handler Interface Contract

**Feature**: 001-shared-agent-invocation
**Handler**: `agentcore_invocation_handler.lambda_handler`
**Runtime**: Python 3.13

## Handler Signature

```python
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Invoke an Amazon Bedrock AgentCore agent with user input.

    Args:
        event: Lambda event (varies by trigger source)
        context: Lambda context object with request_id, function_name, etc.

    Returns:
        dict: AgentInvocationResponse or AgentInvocationError

    Raises:
        No exceptions raised - all errors returned as structured responses
    """
```

## Input Contract

### Event Structure (Direct Invocation)

```json
{
  "agentId": "ABCDE12345",
  "agentAliasId": "FGHIJ67890",
  "sessionId": "123e4567-e89b-12d3-a456-426614174000",
  "inputText": "What is the weather today?",
  "timeout": 30,
  "maxRetries": 3
}
```

### Event Structure (API Gateway)

```json
{
  "body": "{\"agentId\":\"ABCDE12345\",\"agentAliasId\":\"FGHIJ67890\",\"inputText\":\"What is the weather today?\"}",
  "headers": {
    "Content-Type": "application/json"
  },
  "requestContext": {
    "requestId": "api-gateway-request-id",
    "httpMethod": "POST"
  }
}
```

### Event Structure (EventBridge)

```json
{
  "version": "0",
  "id": "event-id",
  "detail-type": "AgentInvocationRequest",
  "source": "custom.agentcore",
  "detail": {
    "agentId": "ABCDE12345",
    "agentAliasId": "FGHIJ67890",
    "inputText": "What is the weather today?"
  }
}
```

### Required Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agentId` | string | Yes | - | Agent identifier (10 alphanumeric) |
| `agentAliasId` | string | Yes | - | Agent alias (10 alphanumeric or TSTALIASID/DRAFT) |
| `inputText` | string | Yes | - | User input (max 25KB) |
| `sessionId` | string | No | auto-generated | Session ID for multi-turn (UUID v4) |
| `timeout` | integer | No | 30 | Timeout in seconds (1-60) |
| `maxRetries` | integer | No | 3 | Max retry attempts (0-5) |

### Validation Rules

1. **agentId**: Must match regex `^[A-Z0-9]{10}$`
2. **agentAliasId**: Must match `^[A-Z0-9]{10}$` OR be "TSTALIASID" or "DRAFT"
3. **sessionId**: If provided, must be valid UUID v4 format
4. **inputText**: Must be non-empty string, ≤25KB when UTF-8 encoded
5. **timeout**: If provided, must be integer 1-60
6. **maxRetries**: If provided, must be integer 0-5

---

## Output Contract

### Success Response

**HTTP Status** (if API Gateway): 200 OK

**Response Body**:
```json
{
  "status": "success",
  "data": {
    "output": "The current weather in San Francisco is 68°F with partly cloudy skies.",
    "sessionId": "123e4567-e89b-12d3-a456-426614174000",
    "citations": [
      {
        "text": "Weather data from NOAA",
        "sourceUrl": "https://weather.gov/...",
        "retrievedReferences": []
      }
    ],
    "trace": {
      "reasoning": "User asked about weather...",
      "knowledgeBaseQueries": ["weather San Francisco"],
      "actions": []
    }
  },
  "metadata": {
    "requestId": "lambda-request-id-12345",
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

### Error Response (Validation)

**HTTP Status** (if API Gateway): 400 Bad Request

**Response Body**:
```json
{
  "status": "error",
  "errorType": "ValidationError",
  "errorMessage": "Invalid agentId format. Expected 10 uppercase alphanumeric characters. Got: 'invalid-id'",
  "errorCode": null,
  "metadata": {
    "requestId": "lambda-request-id-12345",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "agentId": "invalid-id"
  },
  "retryable": false
}
```

### Error Response (Agent Not Found)

**HTTP Status** (if API Gateway): 404 Not Found

**Response Body**:
```json
{
  "status": "error",
  "errorType": "AgentNotFound",
  "errorMessage": "Agent with ID 'ABCDE12345' and alias 'FGHIJ67890' not found. Verify agent exists and is active.",
  "errorCode": "ResourceNotFoundException",
  "metadata": {
    "requestId": "lambda-request-id-12345",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "agentId": "ABCDE12345"
  },
  "retryable": false
}
```

### Error Response (Throttling)

**HTTP Status** (if API Gateway): 429 Too Many Requests

**Response Body**:
```json
{
  "status": "error",
  "errorType": "ThrottlingError",
  "errorMessage": "Request throttled by Bedrock service. Retry after 2 seconds.",
  "errorCode": "ThrottlingException",
  "metadata": {
    "requestId": "lambda-request-id-12345",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "agentId": "ABCDE12345"
  },
  "retryable": true
}
```

### Error Response (Timeout)

**HTTP Status** (if API Gateway): 504 Gateway Timeout

**Response Body**:
```json
{
  "status": "error",
  "errorType": "TimeoutError",
  "errorMessage": "Agent invocation exceeded 30 second timeout. Try reducing input size or increasing timeout parameter.",
  "errorCode": null,
  "metadata": {
    "requestId": "lambda-request-id-12345",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "agentId": "ABCDE12345"
  },
  "retryable": true
}
```

### Error Response (Internal Error)

**HTTP Status** (if API Gateway): 500 Internal Server Error

**Response Body**:
```json
{
  "status": "error",
  "errorType": "InternalError",
  "errorMessage": "AWS Bedrock service error. Contact support with request ID.",
  "errorCode": "InternalServerException",
  "metadata": {
    "requestId": "lambda-request-id-12345",
    "timestamp": "2025-11-11T14:30:00.000Z",
    "agentId": "ABCDE12345"
  },
  "retryable": true
}
```

---

## HTTP Status Code Mapping (API Gateway)

| Scenario | HTTP Status | Error Type |
|----------|-------------|------------|
| Success | 200 OK | - |
| Validation error | 400 Bad Request | ValidationError |
| Agent not found | 404 Not Found | AgentNotFound |
| Throttling | 429 Too Many Requests | ThrottlingError |
| Timeout | 504 Gateway Timeout | TimeoutError |
| Internal error | 500 Internal Server Error | InternalError |
| Unknown error | 500 Internal Server Error | UnknownError |

---

## Side Effects

1. **CloudWatch Logs**: Structured JSON logs written for every invocation
2. **X-Ray Traces**: Trace segments created for Bedrock API calls
3. **Bedrock Session State**: Session created/updated in Bedrock service (not Lambda state)
4. **Token Usage**: Bedrock tokens consumed per invocation (billable)

---

## Idempotency

**Guarantee**: Same input → same output (for deterministic agents)

**Caveats**:
- Agent responses may vary if agent uses non-deterministic models
- Timestamp in metadata will differ per invocation
- Request ID will differ per invocation
- Session state accumulates (subsequent calls with same sessionId see conversation history)

**Recommendation**: Use consistent `sessionId` for conversation continuity, omit `sessionId` for independent queries

---

## Performance Characteristics

- **Cold Start**: ~1000ms (first invocation after deploy or idle)
- **Warm Start**: ~50-100ms Lambda overhead + Bedrock latency
- **Bedrock Latency**: Variable (typically 1-10 seconds for agent reasoning)
- **Total p95**: Target <30 seconds end-to-end

---

## Testing Contract

### Unit Test Requirements

1. **Validation**: Test all validation rules (valid + invalid inputs)
2. **Event Parsing**: Test all event source formats (direct, API Gateway, EventBridge)
3. **Success Path**: Mock Bedrock response, verify correct response structure
4. **Error Handling**: Mock all Bedrock error types, verify error responses
5. **Retry Logic**: Mock throttling, verify exponential backoff
6. **Logging**: Verify structured logs emitted with correct fields
7. **Metadata**: Verify requestId, timestamp, executionTime populated

### Contract Test Requirements

1. **Test Events**: Provide valid test events in `tests/events/`
   - `agentcore-invocation-direct.json`
   - `agentcore-invocation-api-gateway.json`
   - `agentcore-invocation-eventbridge.json`

2. **Schema Validation**: Test response matches schema for all scenarios

### Integration Test Requirements

1. **Live Agent**: Test with real Bedrock agent in dev environment
2. **Session Continuity**: Test multi-turn conversation with same sessionId
3. **Error Scenarios**: Test with invalid agentId, missing permissions
4. **Performance**: Verify p95 latency meets target

---

## Backward Compatibility

**Version**: 1.0.0 (initial release)

**Breaking Changes**: N/A (initial version)

**Future Compatibility**:
- Additional optional parameters can be added without breaking clients
- Response structure may add new optional fields
- Error types may expand (existing types preserved)
- HTTP status codes will remain consistent

---

## Security

1. **IAM Permissions**: Lambda execution role must have `bedrock:InvokeAgent`
2. **Input Sanitization**: All inputs validated before use
3. **Log Sanitization**: PII and sensitive data excluded from logs
4. **No Credentials**: All auth via IAM role (no API keys in code/config)

---

## Example Usage

### Python (boto3)

```python
import boto3
import json

lambda_client = boto3.client('lambda')

response = lambda_client.invoke(
    FunctionName='agentcore-invocation-handler-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'agentId': 'ABCDE12345',
        'agentAliasId': 'FGHIJ67890',
        'inputText': 'What is the weather in SF?'
    })
)

result = json.loads(response['Payload'].read())
if result['status'] == 'success':
    print(result['data']['output'])
else:
    print(f"Error: {result['errorMessage']}")
```

### AWS CLI

```bash
aws lambda invoke \
  --function-name agentcore-invocation-handler-dev \
  --payload '{"agentId":"ABCDE12345","agentAliasId":"FGHIJ67890","inputText":"Hello"}' \
  response.json

cat response.json | jq -r '.data.output'
```

### API Gateway (curl)

```bash
curl -X POST https://api.example.com/invoke-agent \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "ABCDE12345",
    "agentAliasId": "FGHIJ67890",
    "inputText": "What is the weather?"
  }'
```

---

## Conclusion

Lambda handler contract fully defined with input/output schemas, validation rules, error handling, and testing requirements. Ready for implementation following test-first development (Constitution III).
