# Amazon Bedrock AgentCore Lambda Functions

AWS Lambda functions for Amazon Bedrock AgentCore workflows, deployed with AWS SAM.

## Features

- **SQS Email Handler**: Process emails from SES via SQS, invoke Bedrock agent to create GitHub issues
- Three-layer architecture (handlers → services → integrations)
- Multi-environment support (dev, staging, prod)
- X-Ray tracing enabled
- Comprehensive error handling and retry logic

## System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Email to GitHub Issue Flow                          │
└─────────────────────────────────────────────────────────────────────────┘

1. Customer Email
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
   └──► Invoke Bedrock Agent
        │
        ▼
4. Bedrock Agent
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
5. GitHub Issue Created
   │
   └──► Agent returns confirmation with issue URL
        │
        ▼
6. Lambda logs result to CloudWatch
   └──► Response includes GitHub issue URL
```

**Step-by-Step**:

1. **Customer sends email** → `support@yourdomain.com`
2. **Amazon SES receives email** →
   - Stores raw email in S3: `s3://bucket/email/msg-id`
   - Sends notification to SQS queue
3. **SQS triggers Lambda** → Event source mapping invokes `sqs-email-handler`
4. **Lambda processes email** →
   - Fetches email from S3 (`s3_service.fetch_email_from_s3`)
   - Parses MIME content (`email_service.extract_email_body`)
   - Creates prompt with email content
5. **Lambda invokes Bedrock Agent** (`agentcore_invocation.invoke_agent`) →
   - Sends prompt with customer email
   - Agent queries knowledge base for template
   - Agent extracts bug details from email
   - Agent validates required fields exist
6. **Agent creates GitHub issue** →
   - Uses GitHub MCP tools (no GitHub code in Lambda)
   - Formats issue per template
   - Applies appropriate labels
   - Sets severity/priority
7. **Agent returns response** →
   - Confirmation message
   - GitHub issue URL
   - Issue summary
8. **Lambda logs result** → CloudWatch Logs includes agent response and issue URL

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
│   ├── integrations/         # AWS service wrappers (Layer 3)
│   │   └── agentcore_invocation.py
│   ├── services/             # Utilities (Layer 2)
│   │   ├── email.py
│   │   ├── s3.py
│   │   └── prompts.py        # Prompt loader (filesystem + S3)
│   ├── prompts/              # AI agent prompts (packaged with Lambda)
│   │   ├── github_issue.txt
│   │   └── README.md
│   ├── sqs_email_handler.py  # Lambda handler (Layer 1)
│   └── requirements.txt
├── tests/
│   ├── integrations/
│   ├── services/
│   └── events/
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

**Purpose**: Process SES emails from SQS, invoke Bedrock agent to analyze email and create GitHub issues using agent's MCP tools.

**Flow**:
1. SQS triggers Lambda with SES notification
2. Lambda fetches email from S3
3. Parses MIME content (text/HTML body, attachments)
4. Invokes Bedrock agent with email content
5. Agent queries knowledge base for bug report template
6. Agent creates GitHub issue via MCP tools
7. Lambda logs agent response with issue URL

**Configuration** (`src/sqs_email_handler.py:130-323`):
- Default repository: `bugs`
- Agent validates template exists in knowledge base
- Agent validates email has required fields
- Error handling for missing template or incomplete emails

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
