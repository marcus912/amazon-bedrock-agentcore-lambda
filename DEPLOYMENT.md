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
bin/deploy.sh                    # Deploy to dev
ENVIRONMENT=prod bin/deploy.sh   # Deploy to prod
```

## Verify

```bash
# Check function
aws lambda get-function --function-name sqs-email-handler-dev

# View logs (send test email first)
aws logs tail /aws/lambda/sqs-email-handler-dev --follow
```

**Expected logs**:
- Agent invocation STARTED (async)
- Lambda completes in ~1-2s
- Check GitHub for created issue (agent processes in background)

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
