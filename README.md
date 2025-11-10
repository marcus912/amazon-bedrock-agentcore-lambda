# Amazon Bedrock AgentCore Lambda Functions

A collection of AWS Lambda functions for Amazon Bedrock AgentCore workflows, deployed and managed using AWS SAM (Serverless Application Model).

## Overview

This project contains multiple Lambda functions that support various Bedrock AgentCore operations:

- **SES Email Handler**: Process emails from Amazon SES via SQS (parse, extract, process)
- _More Lambda functions coming soon..._

## Features

- Multi-function architecture with shared infrastructure
- Environment support (dev, staging, prod)
- Infrastructure as Code via SAM
- Comprehensive unit tests
- X-Ray tracing enabled
- Cost optimized

## Prerequisites

- [uv](https://docs.astral.sh/uv/) - Python package and project manager
- AWS CLI configured with credentials
- Python 3.13+
- Amazon Bedrock access
- Amazon SES verified domain (for email handler)

## Project Structure

```
.
├── template.yaml              # SAM template (all Lambda functions)
├── samconfig.toml            # Deployment configuration
├── pyproject.toml            # Python project config (uv)
├── uv.lock                   # Locked dependencies
├── src/
│   ├── sqs_email_handler.py  # SES email processing Lambda
│   ├── requirements.txt      # Shared Lambda dependencies
│   └── ...                    # Additional Lambda functions
└── tests/
    ├── test_sqs_email_handler.py
    ├── events/
    └── ...
```

## Quick Start

### Setup

Install dependencies and tools:

```bash
# Install Python dependencies
uv sync --extra dev

# Install AWS SAM CLI (if not already installed)
uv tool install aws-sam-cli
```

### Deploy

```bash
# Build
uv tool run sam build

# Deploy to dev
uv tool run sam deploy --config-env dev

# Deploy to prod
uv tool run sam deploy --config-env prod
```

### Verify Deployment

```bash
aws cloudformation describe-stack-resources \
  --stack-name bedrock-agentcore-lambda-dev \
  --query 'StackResources[?ResourceType==`AWS::Lambda::Function`].[LogicalResourceId,PhysicalResourceId]' \
  --output table
```

## Lambda Functions

### SES Email Handler

Processes emails from Amazon SES via SQS, parses MIME content, and executes business logic.

**Resources:**
- Lambda: `ses-email-handler-{env}`
- SQS Queue: `ses-email-queue-{env}`
- DLQ: `ses-email-dlq-{env}`
- S3 Bucket: `ses-emails-{AccountId}-{env}`

**Post-Deployment Setup:**

Configure SES Receipt Rule to send emails to the created SQS queue and S3 bucket. See stack outputs for ARNs:

```bash
aws cloudformation describe-stacks \
  --stack-name bedrock-agentcore-lambda-dev \
  --query 'Stacks[0].Outputs'
```

**Customization:**

Edit `src/sqs_email_handler.py` function `process_email()` (line 241) to add your business logic.

**Monitoring:**

```bash
# View logs
uv tool run sam logs -n SESEmailHandlerFunction --stack-name bedrock-agentcore-lambda-dev --tail

# Check queue depth
QUEUE_URL=$(aws cloudformation describe-stacks --stack-name bedrock-agentcore-lambda-dev --query 'Stacks[0].Outputs[?OutputKey==`EmailQueueUrl`].OutputValue' --output text)
aws sqs get-queue-attributes --queue-url $QUEUE_URL --attribute-names ApproximateNumberOfMessages
```

### _Additional Functions_

_Documentation for additional Lambda functions will be added as they are implemented._

## Development

### Adding a New Lambda Function

1. Create handler file in `src/my_new_handler.py`
2. Add function resource to `template.yaml`
3. Create tests in `tests/test_my_new_handler.py` and `tests/events/my-new-event.json`
4. Add outputs to `template.yaml`
5. Build, test, deploy: `uv tool run sam build && uv run pytest tests/ -v && uv tool run sam deploy --config-env dev`

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test
uv run pytest tests/test_sqs_email_handler.py -v

# With coverage
uv run pytest tests/ --cov=src --cov-report=html
```

### Local Testing

```bash
# Invoke function locally
uv tool run sam local invoke SESEmailHandlerFunction -e tests/events/sqs-event.json
```

### Adding Dependencies

For development dependencies, add to `pyproject.toml` under `[project.optional-dependencies]`, then sync:

```bash
uv sync --extra dev
```

For Lambda runtime dependencies, add to `src/requirements.txt`, then rebuild:

```bash
uv tool run sam build
uv tool run sam deploy --config-env dev
```

## Configuration

### Environments

Three environments configured in `samconfig.toml`:

- **dev**: Development (requires confirmation)
- **staging**: Pre-production (auto-confirms)
- **prod**: Production (requires confirmation)

### Parameters

Edit `samconfig.toml` to customize per environment (stack name, region, parameters).

### Lambda Defaults

Edit `template.yaml` Globals section for timeout, memory, runtime (python3.13), tracing.

## Deployment

### Deploy to Environments

```bash
uv tool run sam build && uv tool run sam deploy --config-env dev     # Development
uv tool run sam build && uv tool run sam deploy --config-env staging # Staging
uv tool run sam build && uv tool run sam deploy --config-env prod    # Production
```

### Validate Template

```bash
uv tool run sam validate              # Basic validation
uv tool run sam validate --lint       # With linting
```

### Delete Stack

```bash
# Empty S3 buckets first
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name bedrock-agentcore-lambda-dev --query 'Stacks[0].Outputs[?OutputKey==`SESEmailBucketName`].OutputValue' --output text)
aws s3 rm s3://$BUCKET_NAME --recursive

# Delete stack
aws cloudformation delete-stack --stack-name bedrock-agentcore-lambda-dev
```

## Monitoring

### Logs

```bash
# Tail logs for specific function
uv tool run sam logs -n SESEmailHandlerFunction --stack-name bedrock-agentcore-lambda-dev --tail

# Or use AWS CLI
aws logs tail /aws/lambda/ses-email-handler-dev --follow
```

### Metrics

Monitor in CloudWatch:
- Invocation count
- Error rate
- Duration
- Throttles

### X-Ray Tracing

View traces in AWS X-Ray console for:
- Lambda execution time
- AWS service calls (S3, SQS, Bedrock)
- Error traces

## Troubleshooting

### Build Fails

```bash
rm -rf .aws-sam/
uv tool run sam build
```

### Lambda Not Triggered

1. Check CloudWatch Logs for errors
2. Verify IAM permissions
3. Check event source configuration
4. Review metrics for throttling

### Permission Errors

Ensure Lambda roles have required permissions:
- S3: `s3:GetObject`
- SQS: `sqs:ReceiveMessage`, `sqs:DeleteMessage`
- Bedrock: `bedrock:InvokeAgent`

## Security

- Least privilege IAM permissions
- Never hardcode secrets (use Secrets Manager/Parameter Store)
- Enable encryption at rest (S3, SQS)
- Validate and sanitize all inputs
- Use VPC for sensitive workloads

## Cost Estimate

- Lambda: ~$0.20 per 1M requests
- SQS: First 1M/month free, then $0.40 per 1M
- S3: Storage + requests
- CloudWatch: Logs and metrics
- X-Ray: $5 per 1M traces

Typical usage: < $5/month per environment

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Amazon SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/)

## Contributing

When adding new Lambda functions:

1. Follow existing code structure
2. Add comprehensive unit tests
3. Update this README with function documentation
4. Document setup steps and required resources

## License

MIT License
