# Amazon Bedrock AgentCore Lambda Functions

AWS Lambda functions for Amazon Bedrock AgentCore workflows, deployed with AWS SAM.

## Features

- **SQS Email Handler**: Process emails from SES via SQS, invoke Bedrock agent asynchronously to create GitHub issues
- **Async Agent Invocation**: Fire-and-forget pattern - Lambda returns immediately while agent continues processing
- Four-layer architecture (handler → domain → services → integrations)
- Type-safe domain models with dataclasses
- Multi-environment support (dev, staging, prod)
- X-Ray tracing enabled
- Fail-fast error handling (no retries to prevent infinite loops)

## System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Email to GitHub Issue Flow                          │
└─────────────────────────────────────────────────────────────────────────┘

1. Bug Report Email (from Support/QA Team)
   │
   ▼
2. Amazon SES (Simple Email Service)
   ├──► S3 Bucket (stores raw email)
   └──► SQS Queue (sends notification)
        │
        ▼
3. Lambda Function (sqs-email-handler)
   │
   ├──► Fetch email from S3
   ├──► Parse MIME content (text/HTML body, attachments)
   ├──► Start Bedrock Agent (ASYNC - Fire-and-Forget)
   └──► Return immediately (consume SQS message)
        │
        ▼
4. Lambda Complete (< 1 second)
   └──► SQS message deleted

   ┌─────────────────────────────────────────────────────────────┐
   │         Agent Continues Processing (Background)             │
   └─────────────────────────────────────────────────────────────┘
        │
        ▼
5. Bedrock Agent (Runs Independently)
   │
   ├──► Query Knowledge Base
   │    ├── Bug report template
   │    ├── Severity guidelines
   │    └── Product catalog
   │
   ├──► Analyze email content
   │    ├── Extract error messages
   │    ├── Identify product/component
   │    ├── Determine severity
   │    └── Validate required fields
   │
   └──► GitHub MCP Tools
        │
        ▼
6. GitHub Issue Created
   └──► Agent completes (Lambda already finished)
```

**Step-by-Step**:

1. **Support/QA team sends bug report email** → `support@yourdomain.com`
2. **Amazon SES receives email** →
   - Stores raw email in S3: `s3://bucket/email/msg-id`
   - Sends notification to SQS queue
3. **SQS triggers Lambda** → Event source mapping invokes `sqs-email-handler`
4. **Lambda processes email** (< 1 second) →
   - Fetches email from S3 (`s3_service.fetch_email_from_s3`)
   - Parses MIME content (`email_service.extract_email_body`)
   - Creates prompt with email content
5. **Lambda starts Bedrock Agent ASYNCHRONOUSLY** (`agentcore_invocation.invoke_agent_async`) →
   - Sends prompt with bug report email
   - **Does NOT wait for response** (fire-and-forget)
   - **Lambda returns immediately**
   - **SQS message deleted** (consumed)
6. **Agent continues processing in background** →
   - Queries knowledge base for template
   - Extracts bug details from email
   - Validates required fields exist
7. **Agent creates GitHub issue** →
   - Uses GitHub MCP tools (no GitHub code in Lambda)
   - Formats issue per template
   - Applies appropriate labels
   - Sets severity/priority
8. **Agent completes** → GitHub issue created (Lambda already finished)

**Key Benefit**: Lambda execution time reduced from 60-90 seconds to < 1 second. Agent processing happens independently without blocking Lambda or SQS messages.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) - Python package manager
- AWS CLI configured
- Python 3.13+
- SAM CLI
- Bedrock Agent with GitHub MCP tools
- SES verified domain (for email processing)

## Project Structure

```
.
├── bin/
│   ├── deploy.sh             # Deployment script
│   └── update-prompts.sh     # Upload prompts to S3 (optional)
├── src/
│   ├── sqs_email_handler.py  # Lambda handler (thin orchestration, 92 lines)
│   ├── domain/               # Business logic
│   │   ├── models.py         # Type-safe dataclasses (EmailMetadata, etc.)
│   │   └── email_processor.py # Email processing pipeline
│   ├── services/             # Utilities
│   │   ├── email.py          # Email parsing
│   │   ├── s3.py             # S3 operations
│   │   └── prompts.py        # Prompt loader (filesystem + S3)
│   ├── integrations/         # External APIs
│   │   └── agentcore_invocation.py # Bedrock agent client
│   ├── prompts/              # AI agent prompts (packaged with Lambda)
│   │   ├── github_issue.txt
│   │   └── README.md
│   └── requirements.txt
├── tests/
│   ├── test_domain_models.py
│   ├── test_sqs_email_handler.py
│   ├── test_integration_agentcore_invocation.py
│   └── test_service_*.py
├── template.yaml             # SAM infrastructure
└── samconfig.toml           # Deployment config
```

## Quick Start

### 1. Install Dependencies

```bash
uv sync --extra dev
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your AWS resource identifiers
```

### 3. Deploy

```bash
bin/deploy.sh
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Prompt Management

AI agent prompts are packaged with Lambda and can optionally be overridden via S3.

**Loading Strategy**:

1. **Cache** → Use cached version (fast)
2. **S3 Override** → Load from S3 if `PROMPT_BUCKET` set (runtime updates)
3. **Local Filesystem** → Use packaged prompts from `src/prompts/` (always works)

**Update Prompts**:

```bash
# Option 1: Redeploy Lambda (prompts packaged with code)
#  - Edit src/prompts/github_issue.txt
#  - Run: bin/deploy.sh

# Option 2: S3 Override (no redeploy needed!)
#  - Edit src/prompts/github_issue.txt
#  - Run: bin/update-prompts.sh
#  - Next Lambda invocation uses S3 version
```

**Benefits**:
- ✅ **Always works** - Prompts packaged with Lambda
- ✅ **No duplication** - Single source of truth (`src/prompts/github_issue.txt`)
- ✅ **Update without redeploying** - S3 override support
- ✅ **Fast** - Prompts cached in memory
- ✅ **Secure** - No hardcoded sensitive data
- ✅ **Resilient** - Falls back to local filesystem if S3 fails

**S3 Location**: `s3://${PROMPT_BUCKET}/prompts/` (configurable via environment variable)

See [src/prompts/README.md](src/prompts/README.md) for detailed documentation.

## Development

### Run Tests

```bash
uv run pytest tests/ -v

# With coverage
uv run pytest --cov=src --cov-report=html
```

### Local Testing

```bash
# Invoke function locally
sam local invoke SQSEmailHandlerFunction -e tests/events/sqs-event.json
```

### Add Lambda Function

1. Create handler: `src/my_handler.py`
2. Add to `template.yaml`
3. Create tests: `tests/test_my_handler.py`
4. Deploy: `bin/deploy.sh`

## Lambda Functions

### SQS Email Handler

**Purpose**: Process SES emails from SQS, invoke Bedrock agent asynchronously to create GitHub issues using agent's MCP tools.

**Architecture**:
- **Handler** (`sqs_email_handler.py`): Thin orchestration layer (92 lines)
- **Domain** (`domain/email_processor.py`): All business logic
- **Models** (`domain/models.py`): Type-safe data structures

**Flow**:
1. SQS triggers Lambda with SES notification
2. Handler delegates to `EmailProcessor.process_ses_record()`
3. Processor fetches email from S3
4. Parses MIME content (text/HTML body, attachments)
5. **Invokes Bedrock agent ASYNCHRONOUSLY** with email content (fire-and-forget)
6. **Lambda returns immediately** (< 1 second)
7. Agent continues processing in background:
   - Queries knowledge base for bug report template
   - Creates GitHub issue via MCP tools
8. Returns `ProcessingResult` with async confirmation

**Configuration**:
- Default repository: `bugs` (configurable in `EmailProcessor`)
- **Async invocation mode**: Default (use `invoke_agent_async`)
- **Sync invocation mode**: Available via `invoke_agent` (waits for response)
- Fail-fast error handling (no retries)

**Monitor**:
```bash
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

## Configuration

### Environments

- **dev**: Development
- **staging**: Pre-production
- **prod**: Production

Edit `samconfig.toml` for environment-specific settings.

### Parameters

Configure in `.env`:
- `ENVIRONMENT`: Deployment environment
- `AGENT_RUNTIME_ARN`: Bedrock agent ARN
- `SES_EMAIL_BUCKET_NAME`: S3 bucket for SES emails
- `SQS_QUEUE_ARN`: SQS queue ARN

## Monitoring

### CloudWatch Logs

```bash
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

### Metrics

Monitor in CloudWatch:
- Invocation count, error rate, duration
- Throttles, concurrent executions
- SQS queue depth

### X-Ray Tracing

View traces in AWS X-Ray console for service call analysis and error traces.

## Troubleshooting

**Build Fails**:
```bash
rm -rf .aws-sam/
sam build
```

**Lambda Not Triggered**:
- Check CloudWatch Logs for errors
- Verify IAM permissions (S3, SQS, Bedrock)
- Check event source mapping

**Agent Invocation Fails**:
- Verify `AGENT_RUNTIME_ARN` is correct
- Check agent state is `PREPARED`
- Ensure Lambda role has `bedrock-agentcore:InvokeAgentRuntime` permission (for bedrock-agentcore client)

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

## License

MIT License
