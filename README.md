# Amazon Bedrock AgentCore Lambda

AWS Lambda functions for Bedrock AgentCore workflows with AWS SAM.

## Features

- **SQS Email Handler**: SES emails → Bedrock agent → GitHub issues
- **Email Attachments**: Extract and upload attachments to S3/CloudFront for GitHub issue embedding
- Four-layer architecture (handler → domain → services → integrations)
- Type-safe domain models (dataclasses)
- Multi-environment support (dev, qa, prod)
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
bin/deploy.sh                # Interactive - prompts for environment
bin/deploy.sh dev            # Deploy to dev (uses .env or .env.dev)
bin/deploy.sh qa             # Deploy to qa (uses .env.qa)
bin/deploy.sh prod           # Deploy to prod (uses .env.prod)
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for details.

## Prompt Management

Prompts load from: Cache → S3 (if set) → Local filesystem (always works)

S3 path: `s3://{bucket}/prompts/{env}/github_issue.txt`

```bash
# Update via S3 (no redeploy)
bin/update-prompts.sh              # Upload all prompts to dev
bin/update-prompts.sh qa           # Upload all prompts to qa
bin/update-prompts.sh all          # Upload all prompts to ALL environments
bin/update-prompts.sh prod github_issue.txt  # Upload specific to prod

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

Environments: `dev`, `qa`, `prod` (edit `samconfig.toml`)

**Required** in `.env` or SAM parameters:
- `AGENT_RUNTIME_ARN`: Bedrock AgentCore runtime ARN
- `STORAGE_BUCKET_NAME`: S3 bucket for app storage (emails, prompts)
- `SQS_QUEUE_ARN`: SQS queue ARN for email notifications

**Optional**:
- `BEDROCK_READ_TIMEOUT`: Agent timeout in seconds (default: 300 = 5 min)
- `PROMPT_CACHE_TTL`: Prompt cache TTL in seconds (default: 300)

**Attachments** (optional - for email attachment uploads):
- `ATTACHMENTS_S3_BUCKET`: S3 bucket for storing attachments
- `ATTACHMENTS_CLOUDFRONT_DOMAIN`: CloudFront domain for public URLs
- `ATTACHMENT_MAX_SIZE_MB`: Max file size in MB (default: 20)

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
