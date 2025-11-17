# Deployment Guide

## Prerequisites

- AWS CLI configured with appropriate credentials
- SAM CLI installed (`sam --version` to verify)
- Python 3.13+
- Existing AWS resources:
  - S3 bucket for SES emails
  - SQS queue for SES notifications
  - Bedrock Agent with GitHub MCP tools

## Quick Start

### 1. Configure Environment

```bash
# Copy template and fill in your values
cp .env.example .env

# Edit .env with your actual values:
# - ENVIRONMENT=dev
# - AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
# - SES_EMAIL_BUCKET_NAME=your-bucket-name
# - SQS_QUEUE_ARN=arn:aws:sqs:...
```

### 2. Deploy

```bash
# One command deployment
bin/deploy.sh

# Or deploy to specific environment
ENVIRONMENT=staging bin/deploy.sh
```

The script will:
1. Validate all required parameters
2. Build the SAM application
3. Deploy to AWS
4. Display deployment outputs

## Deployment Outputs

After successful deployment:

```
Lambda Function: sqs-email-handler-{env}
Function ARN: arn:aws:lambda:{region}:{account}:function:sqs-email-handler-{env}
SQS Queue: {your-queue-arn}
S3 Bucket: {your-bucket-name}
```

## Verify Deployment

```bash
# Check function exists
aws lambda get-function --function-name sqs-email-handler-dev

# View logs
aws logs tail /aws/lambda/sqs-email-handler-dev --follow

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url https://sqs.{region}.amazonaws.com/{account}/{queue-name} \
  --attribute-names ApproximateNumberOfMessages
```

## Test

Send an email to your SES address, then check logs:

```bash
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

Look for:
- Email processing started
- Agent invocation
- GitHub issue URL in agent response

## Troubleshooting

### Permission Errors

Ensure your IAM user has:
- CloudFormation create/update permissions
- Lambda management permissions
- IAM role creation permissions
- S3 access to deployment bucket

### Agent Invocation Fails

Check:
1. AGENT_RUNTIME_ARN is correct
2. Lambda has `bedrock-agentcore:InvokeAgentRuntime` permission (check template.yaml line 85 - for bedrock-agentcore client)
3. Agent exists and is in `PREPARED` state

### SQS Messages Not Triggering

Verify:
1. SQS queue ARN is correct
2. Event source mapping created (check AWS Console)
3. SQS queue has messages

## Update Deployment

```bash
# Make code changes
# Then redeploy
bin/deploy.sh
```

SAM will detect changes and update the stack.

## Delete Stack

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name bedrock-agentcore-lambda-dev

# Verify deletion
aws cloudformation describe-stacks --stack-name bedrock-agentcore-lambda-dev
```

**Note**: This does NOT delete the S3 bucket, SQS queue, or Bedrock agent (they are externally managed).

## Environments

- **dev**: Development (auto-confirm changeset)
- **staging**: Pre-production (auto-confirm changeset)
- **prod**: Production (requires manual confirmation)

Edit `samconfig.toml` to change environment settings.
