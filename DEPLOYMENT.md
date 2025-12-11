# Deployment Guide

## Prerequisites

- AWS CLI, SAM CLI, Python 3.13+
- Existing: S3 bucket, SQS queue, Bedrock Agent with GitHub MCP tools

## Deploy

```bash
# 1. Configure
cp .env.example .env
# Edit .env with: AGENT_RUNTIME_ARN, SES_EMAIL_BUCKET_NAME, SQS_QUEUE_ARN

# 2. Deploy
bin/deploy.sh                    # Deploy using .env (default)
bin/deploy.sh .env.qa            # Deploy using .env.qa
bin/deploy.sh .env.prod          # Deploy using .env.prod
```

## Verify

```bash
# Check function
aws lambda get-function --function-name sqs-email-handler-dev

# View logs (send test email first)
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

**Expected logs**:
- Agent invocation completed
- Lambda completes in up to 5 min (waits for agent response)
- Check GitHub for created issue

## Multi-Environment Deployment

Each environment is fully isolated with its own CloudFormation stack.

### Environment Isolation

| Resource | Naming Pattern |
|----------|----------------|
| CloudFormation Stack | `bedrock-agentcore-lambda-{env}` |
| Lambda Function | `sqs-email-handler-{env}` |
| IAM Role | Auto-generated per stack |
| S3 Deployment Prefix | `bedrock-agentcore-lambda-{env}` |
| S3 Attachment Path | `attachments/{env}/{message-id}/` |
| S3 Prompt Path | `prompts/{env}/{prompt-name}` |

### Setting Up a New Environment

1. **Create env file** (e.g., `.env.qa`):
   ```bash
   cp .env.example .env.qa
   # Edit with environment-specific values
   ```

2. **Ensure SQS visibility timeout >= Lambda timeout** (300s):
   ```bash
   # Check current timeout
   aws sqs get-queue-attributes \
     --queue-url https://sqs.us-west-2.amazonaws.com/ACCOUNT/QUEUE_NAME \
     --attribute-names VisibilityTimeout

   # Update if needed (360s recommended)
   aws sqs set-queue-attributes \
     --queue-url https://sqs.us-west-2.amazonaws.com/ACCOUNT/QUEUE_NAME \
     --attributes VisibilityTimeout=360
   ```

3. **Deploy**:
   ```bash
   bin/deploy.sh .env.qa
   ```

### Supported Environments

- `dev` - Development (default)
- `qa` - Quality Assurance
- `staging` - Pre-production
- `prod` - Production (requires changeset confirmation)

## Troubleshooting

**Agent fails**:
- Verify `AGENT_RUNTIME_ARN` is correct
- Check agent state is `PREPARED`
- Ensure Lambda role has `bedrock-agentcore:InvokeAgentRuntime`

**Lambda not triggered**:
- Check IAM permissions (S3, SQS, Bedrock)
- Verify event source mapping exists
- Check SQS queue has messages

**Update deployment**: Re-run `bin/deploy.sh` after code changes

**Delete stack**:
```bash
aws cloudformation delete-stack --stack-name bedrock-agentcore-lambda-dev
```
(Does not delete S3 bucket, SQS queue, or Bedrock agent)

## Email Attachments (Optional)

Enable attachment uploads to include images/files in GitHub issues.

### Prerequisites

1. **S3 Bucket**: Public bucket for attachments (separate from email bucket)
2. **CloudFront Distribution**: Origin pointing to attachments bucket

### Configure

Add to your `.env` file:
```bash
ATTACHMENTS_S3_BUCKET=your-attachments-bucket
ATTACHMENTS_CLOUDFRONT_DOMAIN=d1234567890.cloudfront.net
ATTACHMENT_MAX_SIZE_MB=20  # Optional, default: 20
```

### How It Works

1. Lambda extracts attachments from incoming emails
2. Uploads to S3: `attachments/{env}/{message-id}/{filename}`
3. Generates public CloudFront URLs
4. URLs passed to Bedrock agent for inclusion in GitHub issues

Supported: images (PNG, JPEG, GIF), PDFs, CSVs, and other files up to 20 MB (configurable).
