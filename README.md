# Amazon Bedrock AgentCore Lambda

AWS Lambda functions for Bedrock AgentCore workflows with AWS SAM.

## Features

- **SQS Email Handler**: SES emails → Bedrock agent → GitHub issues
- Four-layer architecture (handler → domain → services → integrations)
- Type-safe domain models (dataclasses)
- Multi-environment support (dev, staging, prod)
- Fail-fast error handling (no retries, always consume messages)

## System Flow

```
Email → SES → S3 + SQS → Lambda → Bedrock Agent (up to 5 min) → GitHub Issue
```

**How it works**:
1. SES receives email → saves to S3, notifies SQS
2. Lambda triggered:
   - Fetches email from S3
   - Invokes Bedrock agent synchronously (waits up to 5 minutes)
   - Agent queries knowledge base, creates GitHub issue
   - Returns result, SQS message always consumed (no retries)

## Prerequisites

- Python 3.13+, [uv](https://docs.astral.sh/uv/), SAM CLI, AWS CLI
- Bedrock AgentCore agent with GitHub MCP tools
- SES verified domain

## Quick Start

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Configure (edit .env with your AWS resources)
cp .env.example .env

# 3. Deploy
bin/deploy.sh
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for details.

## Prompt Management

Prompts load from: Cache → S3 (if set) → Local filesystem (always works)

```bash
# Update via S3 (no redeploy)
bin/update-prompts.sh

# Or redeploy with new prompts
bin/deploy.sh
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check .

# Local testing
sam local invoke SQSEmailHandlerFunction -e tests/events/sqs-event.json
```

## Architecture

**Layers**: Handler (thin) → Domain (business logic) → Services (utilities) → Integrations (APIs)

```
src/
├── sqs_email_handler.py      # Handler: thin orchestration
├── domain/
│   ├── email_processor.py    # Domain: business logic
│   └── models.py             # Domain: type-safe dataclasses
├── services/
│   ├── email.py              # Services: email parsing
│   ├── s3.py                 # Services: S3 operations
│   └── prompts.py            # Services: prompt management
├── integrations/
│   └── agentcore_invocation.py  # Integrations: Bedrock API
└── prompts/
    └── github_issue.txt      # Prompt templates
```

**Key patterns**:
- Type-safe models (EmailMetadata, EmailContent, ProcessingResult)
- Module-level boto3 clients (thread-safe, reused across invocations)
- Fail-fast (no retries, strict timeouts)
- Always consume SQS messages (empty batchItemFailures)

**Monitor**:
```bash
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

## Configuration

Environments: `dev`, `staging`, `prod` (edit `samconfig.toml`)

**Required** in `.env` or SAM parameters:
- `AGENT_RUNTIME_ARN`: Bedrock AgentCore runtime ARN
- `SES_EMAIL_BUCKET_NAME`: S3 bucket where SES stores emails
- `SQS_QUEUE_ARN`: SQS queue ARN for email notifications

**Optional**:
- `BEDROCK_READ_TIMEOUT`: Agent timeout in seconds (default: 300 = 5 min)
- `PROMPT_CACHE_TTL`: Prompt cache TTL in seconds (default: 300)

## Troubleshooting

```bash
# Build fails
rm -rf .aws-sam/ && sam build

# Check logs
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

**Common issues**:
- Agent fails → Verify `AGENT_RUNTIME_ARN`, check agent is `PREPARED`
- Lambda timeout → Increase `BedrockReadTimeout` parameter (max 900s)
- Lambda not triggered → Check IAM permissions, event source mapping
- Verify Lambda role has `bedrock-agentcore:InvokeAgentRuntime`
