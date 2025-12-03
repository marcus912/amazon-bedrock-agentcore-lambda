# Amazon Bedrock AgentCore Lambda

AWS Lambda functions for Bedrock AgentCore workflows with AWS SAM.

## Features

- **Async Agent Invocation**: Fire-and-forget pattern, Lambda returns in ~1-2s (vs 60-90s sync)
- **SQS Email Handler**: SES emails → Bedrock agent → GitHub issues
- Four-layer architecture (handler → domain → services → integrations)
- Type-safe domain models
- Multi-environment support (dev, staging, prod)
- Fail-fast error handling (no retries)

## System Flow

```
Email → SES → S3 + SQS → Lambda (1-2s) → Bedrock Agent (60-90s, async) → GitHub Issue
                           ↓
                    Returns immediately
                    SQS message deleted
```

**How it works**:
1. SES receives email → saves to S3, notifies SQS
2. Lambda triggered:
   - Fetches email from S3
   - Starts Bedrock agent (async, fire-and-forget)
   - Returns in ~1-2s, SQS message consumed
3. Agent processes independently:
   - Queries knowledge base
   - Creates GitHub issue via MCP tools

**Key benefit**: Lambda returns in 1-2s (vs 60-90s sync), SQS messages consumed immediately.

## Prerequisites

- Python 3.13+, [uv](https://docs.astral.sh/uv/), SAM CLI, AWS CLI
- Bedrock Agent with GitHub MCP tools
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

# Local testing
sam local invoke SQSEmailHandlerFunction -e tests/events/sqs-event.json
```

## Architecture

**Layers**: Handler (thin) → Domain (business logic) → Services (utilities) → Integrations (APIs)

**SQS Email Handler**:
- Parses SES notification, fetches email from S3
- Invokes Bedrock agent async (fire-and-forget)
- Returns immediately, agent processes independently

**Monitor**:
```bash
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

## Configuration

Environments: `dev`, `staging`, `prod` (edit `samconfig.toml`)

Required in `.env`:
- `AGENT_RUNTIME_ARN`: Bedrock agent ARN
- `SES_EMAIL_BUCKET_NAME`: S3 bucket
- `SQS_QUEUE_ARN`: SQS queue ARN

## Troubleshooting

```bash
# Build fails
rm -rf .aws-sam/ && sam build

# Check logs
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

**Common issues**:
- Agent fails → Verify `AGENT_RUNTIME_ARN`, check agent is `PREPARED`
- Lambda not triggered → Check IAM permissions, event source mapping
- Verify Lambda role has `bedrock-agentcore:InvokeAgentRuntime`
