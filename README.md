# SES Email Handler Lambda

A simple AWS Lambda function that processes emails from Amazon SES via SQS. Emails are stored in S3, fetched by the Lambda, parsed, and processed according to your business logic.

## Architecture

```
Amazon SES → S3 Bucket (email storage)
            ↓
            SQS Queue → Lambda Function
            ↓
            DLQ (failed messages)
```

## Features

- Automatic email processing from SES via SQS
- Parse MIME emails (text, HTML, attachments)
- S3 storage for email content
- Dead Letter Queue for failed messages
- Multiple environments (dev, staging, prod)
- X-Ray tracing enabled
- Comprehensive error handling

## Prerequisites

1. **AWS CLI** configured with credentials
2. **AWS SAM CLI** installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
3. **Python 3.12** or later
4. **Amazon SES** verified domain or email address

## Project Structure

```
.
├── template.yaml              # SAM template
├── samconfig.toml            # Deployment configuration
├── src/
│   ├── sqs_email_handler.py  # Main Lambda function
│   └── requirements.txt      # Lambda dependencies (currently empty)
├── tests/
│   ├── test_sqs_email_handler.py  # Unit tests
│   └── events/
│       └── sqs-event.json    # Sample SQS event
├── requirements-dev.txt      # Development dependencies
└── README.md                 # This file
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-dev.txt
```

### 2. Deploy to AWS

```bash
# Build the application
sam build

# Deploy to dev environment
sam deploy --config-env dev

# Or deploy to prod
sam deploy --config-env prod
```

The deployment will create:
- Lambda function: `ses-email-handler-{env}`
- SQS Queue: `ses-email-queue-{env}`
- Dead Letter Queue: `ses-email-dlq-{env}`
- S3 Bucket: `ses-emails-{AccountId}-{env}`

### 3. Configure SES Receipt Rule

After deployment, configure SES to send emails to the created resources:

```bash
# Get the stack outputs
aws cloudformation describe-stacks \
  --stack-name ses-email-handler-dev \
  --query 'Stacks[0].Outputs'
```

Create an SES Receipt Rule:

1. Go to SES Console → Email receiving → Receipt rules
2. Create a new rule set (or use existing)
3. Add rule with:
   - **Recipients**: Your verified domain/email
   - **Actions**:
     - **S3 Action**: Use bucket name from stack output `SESEmailBucketName`
     - **SQS Action**: Use queue ARN from stack output `EmailQueueArn`

Or use AWS CLI:

```bash
# Variables from stack outputs
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ses-email-handler-dev --query 'Stacks[0].Outputs[?OutputKey==`SESEmailBucketName`].OutputValue' --output text)
QUEUE_ARN=$(aws cloudformation describe-stacks --stack-name ses-email-handler-dev --query 'Stacks[0].Outputs[?OutputKey==`EmailQueueArn`].OutputValue' --output text)

# Create receipt rule (adjust to your needs)
aws ses create-receipt-rule \
  --rule-set-name my-rule-set \
  --rule '{
    "Name": "process-emails",
    "Enabled": true,
    "Recipients": ["your-email@yourdomain.com"],
    "Actions": [
      {
        "S3Action": {
          "BucketName": "'$BUCKET_NAME'"
        }
      },
      {
        "SQSAction": {
          "QueueArn": "'$QUEUE_ARN'"
        }
      }
    ]
  }'
```

## Local Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=html
```

### Invoke Locally

```bash
# Invoke with sample event
sam local invoke SESEmailHandlerFunction -e tests/events/sqs-event.json

# Note: Local invocation will fail on S3 fetch unless you:
# 1. Have AWS credentials configured
# 2. Have the S3 object available
# 3. Or mock the S3 call in your test
```

## Customization

### Add Your Business Logic

Edit `src/sqs_email_handler.py` in the `process_email()` function (around line 286):

```python
def process_email(
    subject: str,
    from_address: str,
    to_addresses: list,
    timestamp: str,
    text_body: str,
    html_body: str,
    attachments: list,
    ses_notification: dict
) -> None:
    """Add your business logic here."""

    # Example 1: Save to DynamoDB
    # save_to_dynamodb({...})

    # Example 2: Create support ticket
    # if 'bug' in subject.lower():
    #     create_support_ticket({...})

    # Example 3: Extract product info
    # product_info = extract_product_details(body)

    # Example 4: Send to Slack
    # send_to_slack(channel='#support', message=f'New email: {subject}')
```

### Add Lambda Dependencies

If you need additional packages (e.g., `requests`, `pydantic`):

1. Edit `src/requirements.txt`:
   ```
   requests>=2.31.0
   pydantic>=2.0.0
   ```

2. Rebuild and redeploy:
   ```bash
   sam build
   sam deploy --config-env dev
   ```

## Monitoring

### View Logs

```bash
# Tail logs in real-time
sam logs -n SESEmailHandlerFunction --stack-name ses-email-handler-dev --tail

# Or use AWS CLI
aws logs tail /aws/lambda/ses-email-handler-dev --follow
```

### Check SQS Queue

```bash
# Get queue URL
QUEUE_URL=$(aws cloudformation describe-stacks \
  --stack-name ses-email-handler-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`EmailQueueUrl`].OutputValue' \
  --output text)

# Check queue attributes
aws sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names All

# Check DLQ for failed messages
DLQ_URL=$(aws sqs get-queue-url --queue-name ses-email-dlq-dev --query 'QueueUrl' --output text)
aws sqs receive-message --queue-url $DLQ_URL
```

### X-Ray Tracing

View traces in AWS X-Ray console to analyze:
- Lambda execution time
- S3 fetch latency
- Error traces

## Configuration

### Environments

The project supports three environments configured in `samconfig.toml`:

- **dev**: Development (requires confirmation before deploy)
- **staging**: Pre-production (auto-confirms changes)
- **prod**: Production (requires confirmation)

### Parameters

Edit `samconfig.toml` to customize:

```toml
[dev.deploy.parameters]
stack_name = "ses-email-handler-dev"
parameter_overrides = "Environment=\"dev\""
region = "us-west-2"  # Change region here
```

### Lambda Configuration

Edit `template.yaml` to adjust:

```yaml
Globals:
  Function:
    Timeout: 30          # Execution timeout
    MemorySize: 256      # Memory allocation
    Runtime: python3.12  # Python version
```

## Deployment

### Deploy to Different Environments

```bash
# Development
sam build && sam deploy --config-env dev

# Staging
sam build && sam deploy --config-env staging

# Production
sam build && sam deploy --config-env prod
```

### Update Existing Stack

```bash
# Build
sam build

# Deploy (will show changes for confirmation)
sam deploy --config-env prod
```

### Delete Stack

```bash
# Delete development stack
aws cloudformation delete-stack --stack-name ses-email-handler-dev

# Note: S3 bucket must be empty first
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ses-email-handler-dev --query 'Stacks[0].Outputs[?OutputKey==`SESEmailBucketName`].OutputValue' --output text)
aws s3 rm s3://$BUCKET_NAME --recursive
aws cloudformation delete-stack --stack-name ses-email-handler-dev
```

## Troubleshooting

### Lambda Not Receiving Messages

1. Check SES Receipt Rule is active:
   ```bash
   aws ses describe-receipt-rule-set --rule-set-name my-rule-set
   ```

2. Verify SQS permissions allow SES to send:
   ```bash
   aws sqs get-queue-attributes --queue-url $QUEUE_URL --attribute-names Policy
   ```

3. Check CloudWatch Logs for errors:
   ```bash
   aws logs tail /aws/lambda/ses-email-handler-dev --follow
   ```

### S3 Access Denied

Ensure Lambda has permission to read from S3 bucket:
- Lambda execution role includes `s3:GetObject` permission
- S3 bucket policy allows SES to write: `s3:PutObject`

### Messages in DLQ

Check the Dead Letter Queue for failed messages:

```bash
# Get DLQ messages
DLQ_URL=$(aws sqs get-queue-url --queue-name ses-email-dlq-dev --query 'QueueUrl' --output text)
aws sqs receive-message --queue-url $DLQ_URL --max-number-of-messages 10

# Process and delete a message
aws sqs delete-message --queue-url $DLQ_URL --receipt-handle "RECEIPT_HANDLE"
```

### Test Email Processing

Send a test email to your configured recipient address:

```bash
# If using SES sandbox, both sender and recipient must be verified
aws ses send-email \
  --from verified-sender@yourdomain.com \
  --to your-recipient@yourdomain.com \
  --subject "Test Email" \
  --text "This is a test email for Lambda processing."
```

## Cost Considerations

- **Lambda**: Pay per invocation and duration (~$0.20 per 1M requests)
- **SQS**: First 1M requests/month free, then $0.40 per 1M
- **S3**: Storage ($0.023/GB) + requests
- **CloudWatch**: Logs and metrics (minimal)
- **X-Ray**: $5 per 1M traces recorded

Estimated cost for 10,000 emails/month: < $1

## Security Best Practices

1. **Verify SES Senders**: Only accept emails from verified domains
2. **Scan for Viruses**: SES virus scanning is enabled by default
3. **Monitor DLQ**: Set up CloudWatch alarms for DLQ depth
4. **Encrypt S3**: Enable S3 encryption at rest (add to template.yaml)
5. **Least Privilege**: Lambda has minimal required permissions

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy SES Email Handler

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: aws-actions/setup-sam@v2
      - uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2

      - name: Build and Deploy
        run: |
          sam build
          sam deploy --config-env prod --no-confirm-changeset
```

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Amazon SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/)
- [SQS Lambda Integration](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Python Email Parser](https://docs.python.org/3/library/email.parser.html)

## License

MIT License
