# Amazon Bedrock AgentCore Lambda with SAM + CodeDeploy

This project deploys a Python Lambda function to invoke Amazon Bedrock AgentCore agents with **safe A/B testing and gradual rollout** using AWS SAM and CodeDeploy.

## Features

- **Automated Canary Deployments**: Shifts 10% traffic first, then gradually rolls out
- **Automatic Rollback**: Monitors CloudWatch alarms and rolls back on errors
- **Pre/Post-Deployment Hooks**: Validates new versions before and after traffic shift
- **Multiple Environments**: Separate dev, staging, and prod configurations
- **CloudWatch Monitoring**: Built-in alarms for errors and throttles
- **X-Ray Tracing**: Distributed tracing enabled by default

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                     CodeDeploy                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │  1. Pre-Traffic Hook (Validation)               │  │
│  │  2. Shift 10% traffic to new version            │  │
│  │  3. Wait 5 minutes + Monitor CloudWatch         │  │
│  │  4. If alarms trigger → Rollback                │  │
│  │  5. Shift remaining 90% traffic                 │  │
│  │  6. Post-Traffic Hook (Final validation)        │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
           ↓                                    ↓
    Lambda v1 (90%)                      Lambda v2 (10%)
           ↓                                    ↓
           └────────────────┬───────────────────┘
                            ↓
                   Bedrock AgentCore
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **AWS SAM CLI** installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
3. **Python 3.12** or later
4. **Bedrock Agent** already created in AWS Bedrock

## Project Structure

```
.
├── template.yaml              # SAM template with CodeDeploy config
├── samconfig.toml            # SAM deployment configuration
├── Makefile                  # Convenience commands
├── src/
│   ├── handler.py            # Main Lambda function
│   └── requirements.txt      # Python dependencies
├── hooks/
│   ├── pre_traffic.py        # Pre-deployment validation
│   └── post_traffic.py       # Post-deployment validation
├── events/
│   └── test-event.json       # Sample test event
└── tests/
    └── test_handler.py       # Unit tests
```

## Quick Start

### 1. Install Dependencies

```bash
pip install aws-sam-cli boto3
```

### 2. Configure Your Agent ID

Edit `samconfig.toml` and set your Bedrock Agent ID:

```toml
parameter_overrides = "Environment=\"dev\" BedrockAgentId=\"YOUR_AGENT_ID\" BedrockAgentAliasId=\"YOUR_ALIAS_ID\""
```

### 3. Build and Deploy

```bash
# Build the application
sam build

# Deploy to dev environment
sam deploy --config-env dev

# Or use the Makefile
make deploy-dev
```

### 4. Test Your Function

```bash
# Invoke locally
sam local invoke BedrockAgentFunction -e events/test-event.json

# Or directly invoke deployed function
aws lambda invoke \
  --function-name bedrock-agentcore-dev:live \
  --payload '{"sessionId":"test","inputText":"Hello"}' \
  response.json
```

## Deployment Options

### Development (Quick Iterations)

```bash
make deploy-dev
```

- Confirms changeset before deploying
- Uses `Canary10Percent5Minutes` (10% for 5 min, then 100%)

### Staging (Pre-Production Testing)

```bash
make deploy-staging
```

- No confirmation required (faster)
- Same canary deployment as dev

### Production (Safe Rollout)

```bash
make deploy-prod
```

- Requires changeset confirmation
- Monitors error and throttle alarms
- Automatic rollback on issues

## Canary Deployment Types

You can change the deployment strategy in `template.yaml`:

```yaml
DeploymentPreference:
  Type: Canary10Percent5Minutes  # Change this
```

Available options:
- `Canary10Percent5Minutes` - 10% for 5 min, then 90%
- `Canary10Percent10Minutes` - 10% for 10 min, then 90%
- `Canary10Percent30Minutes` - 10% for 30 min, then 90%
- `Linear10PercentEvery1Minute` - +10% every minute
- `Linear10PercentEvery10Minutes` - +10% every 10 minutes
- `AllAtOnce` - Immediate deployment (no canary)

## A/B Testing with Lambda Aliases

After deployment, you can manually control traffic split:

```bash
# Get the latest two versions
FUNCTION_NAME="bedrock-agentcore-dev"
VERSION_1=$(aws lambda list-versions-by-function --function-name $FUNCTION_NAME --query 'Versions[-2].Version' --output text)
VERSION_2=$(aws lambda list-versions-by-function --function-name $FUNCTION_NAME --query 'Versions[-1].Version' --output text)

# Split traffic: 80% to v1, 20% to v2
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name live \
  --routing-config "AdditionalVersionWeights={\"$VERSION_2\"=0.2}"

# Shift more traffic to v2
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name live \
  --routing-config "AdditionalVersionWeights={\"$VERSION_2\"=0.5}"

# Complete rollout to v2
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name live \
  --function-version $VERSION_2 \
  --routing-config "{}"
```

## Monitoring

### View Logs

```bash
# Tail logs for dev environment
sam logs -n BedrockAgentFunction --stack-name bedrock-agentcore-lambda-dev --tail

# Or use AWS CLI
aws logs tail /aws/lambda/bedrock-agentcore-dev --follow
```

### Check CloudWatch Alarms

```bash
# List alarms
aws cloudwatch describe-alarms --alarm-name-prefix bedrock-agentcore

# Check alarm history
aws cloudwatch describe-alarm-history --alarm-name bedrock-agentcore-lambda-dev-errors
```

### View Deployment Status

```bash
# List deployments
aws deploy list-deployments --application-name bedrock-agentcore-lambda-dev

# Get deployment details
aws deploy get-deployment --deployment-id d-XXXXX
```

## Testing

### Run Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run tests
pytest tests/ -v
```

### Load Testing

For A/B testing validation, you can use tools like:

```bash
# Simple load test with parallel requests
seq 1 100 | xargs -I {} -P 10 aws lambda invoke \
  --function-name bedrock-agentcore-dev:live \
  --payload '{"sessionId":"test-{}","inputText":"Hello"}' \
  /dev/null
```

## Rollback

If a deployment fails, CodeDeploy automatically rolls back. To manually rollback:

```bash
# Get deployment ID
DEPLOYMENT_ID=$(aws deploy list-deployments --application-name bedrock-agentcore-lambda-dev --query 'deployments[0]' --output text)

# Stop deployment (triggers rollback)
aws deploy stop-deployment --deployment-id $DEPLOYMENT_ID --auto-rollback-enabled
```

## Cost Considerations

- **Lambda**: Pay per request + duration
- **CodeDeploy**: Free for Lambda
- **CloudWatch**: Logs + Alarms (minimal cost)
- **X-Ray**: Pay per trace recorded
- **Bedrock**: Pay per API call + tokens

Canary deployments temporarily run two versions, but cost impact is minimal.

## Customization

### Modify Deployment Hooks

Edit `hooks/pre_traffic.py` to add custom validation:

```python
# Add your custom tests
def validate_bedrock_response(response):
    # Check response quality
    # Validate latency
    # Test specific scenarios
    pass
```

### Add CloudWatch Alarms

In `template.yaml`, add custom alarms:

```yaml
DurationAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    MetricName: Duration
    Threshold: 30000  # 30 seconds
    ComparisonOperator: GreaterThanThreshold
```

### Enable API Gateway

Uncomment the API Gateway section in `template.yaml` to expose HTTP endpoint:

```yaml
BedrockApi:
  Type: AWS::Serverless::Api
  Properties:
    StageName: !Ref Environment
```

## Troubleshooting

### Deployment Failed

Check CloudWatch Logs:
```bash
sam logs -n BedrockAgentFunction --stack-name bedrock-agentcore-lambda-dev
```

### Pre-Traffic Hook Failed

The hook validates the new version before traffic shift. Check:
1. Lambda has correct IAM permissions for Bedrock
2. Agent ID and Alias ID are correct
3. Hook function logs for specific errors

### Automatic Rollback Triggered

Check which alarm triggered:
```bash
aws cloudwatch describe-alarm-history \
  --alarm-name bedrock-agentcore-lambda-dev-errors \
  --start-date 2024-01-01
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy Lambda
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: aws-actions/setup-sam@v2
      - name: Deploy
        run: |
          sam build
          sam deploy --config-env prod --no-confirm-changeset
```

### AWS CodePipeline

Create a pipeline with:
1. **Source**: GitHub/CodeCommit
2. **Build**: CodeBuild with `sam build`
3. **Deploy**: CloudFormation deploy action

## Best Practices

1. **Always test in dev first** before deploying to prod
2. **Monitor CloudWatch Logs** during canary deployments
3. **Set appropriate alarm thresholds** for your traffic patterns
4. **Use X-Ray** to trace Bedrock API calls
5. **Keep pre-traffic hooks fast** (< 60 seconds)
6. **Test rollback procedures** in non-prod environments

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [CodeDeploy for Lambda](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-steps-lambda.html)
- [Bedrock Agent Runtime API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvokeAgent.html)
- [Lambda Aliases](https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html)

## License

MIT License
