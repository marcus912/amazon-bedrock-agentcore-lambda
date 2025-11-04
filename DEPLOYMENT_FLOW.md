# SAM + CodeDeploy Deployment Flow

This document explains how SAM CLI automatically triggers CodeDeploy for safe A/B deployments.

## Overview

When you run `sam deploy`, SAM automatically orchestrates a CodeDeploy canary deployment. You don't need to call CodeDeploy directly - SAM handles everything.

## The Complete Flow

```
Developer                SAM CLI              CloudFormation         CodeDeploy           Lambda
    |                       |                       |                     |                  |
    |--sam build----------->|                       |                     |                  |
    |                       |                       |                     |                  |
    |--sam deploy---------->|                       |                     |                  |
    |                       |                       |                     |                  |
    |                       |--Package & Upload---->|                     |                  |
    |                       |   to S3               |                     |                  |
    |                       |                       |                     |                  |
    |                       |--Create/Update------->|                     |                  |
    |                       |   Stack               |                     |                  |
    |                       |                       |                     |                  |
    |                       |                       |--Create Lambda----->|                  |
    |                       |                       |   Function          |                  |
    |                       |                       |                     |----------------->|
    |                       |                       |                     |   Version 2      |
    |                       |                       |                     |                  |
    |                       |                       |--Create CodeDeploy->|                  |
    |                       |                       |   Application       |                  |
    |                       |                       |                     |                  |
    |                       |                       |--Trigger----------->|                  |
    |                       |                       |   Deployment        |                  |
    |                       |                       |                     |                  |
    |                       |                       |                     |--Pre-Traffic---->|
    |                       |                       |                     |   Hook Test      |
    |                       |                       |                     |<-----------------|
    |                       |                       |                     |   Success        |
    |                       |                       |                     |                  |
    |                       |                       |                     |--Shift 10%------>|
    |                       |                       |                     |   to v2          |
    |                       |                       |                     |                  |
    |                       |                       |                     |-- Wait 5 min --->|
    |                       |                       |                     |   Monitor        |
    |                       |                       |                     |   Alarms         |
    |                       |                       |                     |                  |
    |                       |                       |                     |--Shift 90%------>|
    |                       |                       |                     |   to v2          |
    |                       |                       |                     |                  |
    |                       |                       |                     |--Post-Traffic--->|
    |                       |                       |                     |   Hook Test      |
    |                       |                       |                     |<-----------------|
    |                       |                       |                     |   Success        |
    |                       |                       |                     |                  |
    |<--Deployment Complete-|<----------------------|<--------------------|                  |
```

## Step-by-Step Breakdown

### 1. Developer Initiates Deployment

```bash
# Build the application
sam build

# Deploy to dev environment
sam deploy --config-env dev
```

### 2. SAM CLI Processes

- Validates `template.yaml`
- Packages Lambda code and dependencies
- Uploads artifacts to S3
- Prepares CloudFormation changeset

### 3. SAM Detects Deployment Configuration

In `template.yaml`, SAM sees:

```yaml
BedrockAgentFunction:
  Type: AWS::Serverless::Function
  Properties:
    AutoPublishAlias: live              # ← Triggers CodeDeploy
    DeploymentPreference:               # ← Configures deployment
      Type: Canary10Percent5Minutes
      Alarms:
        - !Ref FunctionErrorAlarm
      Hooks:
        PreTraffic: !Ref PreTrafficHook
        PostTraffic: !Ref PostTrafficHook
```

### 4. CloudFormation Creates Resources

SAM transforms the template into CloudFormation, which creates:

```
Resources Created:
├── AWS::Lambda::Function (bedrock-agentcore-dev)
├── AWS::Lambda::Version (auto-incremented: 1, 2, 3...)
├── AWS::Lambda::Alias (live)
├── AWS::CodeDeploy::Application (ServerlessDeploymentApplication)
├── AWS::CodeDeploy::DeploymentGroup
├── AWS::CloudWatch::Alarm (errors, throttles)
├── Pre-traffic Hook Lambda
└── Post-traffic Hook Lambda
```

### 5. CodeDeploy Executes Canary Deployment

#### Phase 1: Pre-Traffic Validation (0-1 minute)

```
CodeDeploy invokes: hooks/pre_traffic.py
├── Tests new Lambda version
├── Validates response format
├── Checks error rates
└── Reports status to CodeDeploy
```

**If validation fails**: Deployment stops, no traffic shifted

**If validation succeeds**: Proceed to traffic shift

#### Phase 2: Initial Traffic Shift (1 minute)

```
Lambda Alias "live" configuration:
├── Version 1 (old): 90% traffic
└── Version 2 (new): 10% traffic
```

Real requests are now split between versions.

#### Phase 3: Monitoring Period (5 minutes)

CodeDeploy monitors CloudWatch alarms:
- **FunctionErrorAlarm**: Triggers if >5 errors in 2 minutes
- **FunctionThrottleAlarm**: Triggers if >3 throttles in 2 minutes

```
Monitoring:
├── CloudWatch collects metrics from both versions
├── Alarms evaluate thresholds every 60 seconds
└── If alarm triggers → Automatic rollback
```

#### Phase 4: Complete Traffic Shift (6 minutes)

If no alarms triggered:

```
Lambda Alias "live" updated:
├── Version 1 (old): 0% traffic  [deprecated]
└── Version 2 (new): 100% traffic
```

#### Phase 5: Post-Traffic Validation (6-7 minutes)

```
CodeDeploy invokes: hooks/post_traffic.py
├── Validates CloudWatch metrics
├── Checks for any anomalies
└── Reports final status to CodeDeploy
```

**If validation fails**: Triggers rollback to Version 1

**If validation succeeds**: Deployment complete

### 6. Deployment Complete

```bash
Successfully created/updated stack - bedrock-agentcore-lambda-dev
```

Your new code is now handling 100% of traffic.

## What Gets Created in AWS Console

### CodeDeploy Console

Navigate to: **AWS Console → CodeDeploy → Applications**

You'll see:
- **Application Name**: `ServerlessDeploymentApplication`
- **Deployment Group**: `bedrock-agentcore-lambda-dev-DeploymentGroup-XXX`
- **Deployment History**: Shows all canary deployments

### Lambda Console

Navigate to: **AWS Console → Lambda → Functions → bedrock-agentcore-dev**

You'll see:
- **Versions**: 1, 2, 3, 4... (auto-created on each deploy)
- **Aliases**: `live` (points to current production version)
- **Alias Configuration**: Shows traffic weights during canary

### CloudWatch Console

Navigate to: **AWS Console → CloudWatch → Alarms**

You'll see:
- `bedrock-agentcore-lambda-dev-errors`
- `bedrock-agentcore-lambda-dev-throttles`

## Monitoring Active Deployment

### Watch CloudFormation Stack

```bash
# Monitor stack events in real-time
aws cloudformation describe-stack-events \
  --stack-name bedrock-agentcore-lambda-dev \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
  --output table
```

### Watch CodeDeploy Deployment

```bash
# List recent deployments
aws deploy list-deployments \
  --application-name ServerlessDeploymentApplication \
  --max-items 5

# Get specific deployment details
aws deploy get-deployment \
  --deployment-id d-XXXXXXXXX

# Watch deployment status (refresh every 10 seconds)
watch -n 10 'aws deploy get-deployment --deployment-id d-XXXXXXXXX --query "deploymentInfo.status"'
```

### Monitor Lambda Alias Traffic Split

```bash
# Check current traffic routing
aws lambda get-alias \
  --function-name bedrock-agentcore-dev \
  --name live \
  --query '[FunctionVersion,RoutingConfig]'

# Example output during canary:
# [
#   "2",                                    # Primary version
#   {
#     "AdditionalVersionWeights": {
#       "1": 0.9                            # 90% to version 1
#     }
#   }
# ]
```

### Tail Lambda Logs

```bash
# Watch logs from both versions
sam logs -n BedrockAgentFunction --stack-name bedrock-agentcore-lambda-dev --tail

# Or use AWS CLI
aws logs tail /aws/lambda/bedrock-agentcore-dev --follow
```

## Rollback Scenarios

### Automatic Rollback (Alarm Triggered)

If CloudWatch alarms trigger during the 5-minute monitoring period:

```
Timeline:
0:00 - Pre-traffic validation passes
0:01 - Traffic shifted to 10% v2 / 90% v1
0:03 - Error rate spikes on v2
0:04 - FunctionErrorAlarm enters ALARM state
0:04 - CodeDeploy detects alarm
0:05 - CodeDeploy automatically rolls back
0:05 - Traffic reverted to 100% v1
```

**What happens**:
- Alias immediately reverted to Version 1
- Version 2 remains available but receives no traffic
- Deployment marked as `FAILED` in CodeDeploy
- CloudFormation stack update completes (with rollback)

### Manual Rollback

Stop an in-progress deployment:

```bash
# Get deployment ID
DEPLOYMENT_ID=$(aws deploy list-deployments \
  --application-name ServerlessDeploymentApplication \
  --query 'deployments[0]' \
  --output text)

# Stop deployment (triggers rollback)
aws deploy stop-deployment \
  --deployment-id $DEPLOYMENT_ID \
  --auto-rollback-enabled
```

### Rollback to Previous Version

After a successful deployment, manually rollback:

```bash
# List versions
aws lambda list-versions-by-function \
  --function-name bedrock-agentcore-dev

# Update alias to previous version
aws lambda update-alias \
  --function-name bedrock-agentcore-dev \
  --name live \
  --function-version 1 \
  --routing-config '{}'
```

## Manual A/B Testing (Custom Traffic Split)

After deployment completes, you can manually control traffic split:

### Gradual Rollout

```bash
FUNCTION_NAME="bedrock-agentcore-dev"

# Start with 20% on new version
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name live \
  --routing-config 'AdditionalVersionWeights={"2"=0.2}'

# After monitoring, increase to 50%
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name live \
  --routing-config 'AdditionalVersionWeights={"2"=0.5}'

# Complete rollout to new version
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name live \
  --function-version 2 \
  --routing-config '{}'
```

### A/B Test for Extended Period

```bash
# Keep 30% on new version for 1 week
aws lambda update-alias \
  --function-name bedrock-agentcore-dev \
  --name live \
  --routing-config 'AdditionalVersionWeights={"2"=0.3}'

# Monitor metrics in CloudWatch
# Compare error rates, latency, cost between versions
# Analyze Bedrock response quality

# After analysis, decide to rollout or rollback
```

## Key Configuration Options

### Deployment Types

Change in `template.yaml`:

```yaml
DeploymentPreference:
  Type: Canary10Percent5Minutes    # Options below
```

Available types:
- `Canary10Percent5Minutes` - 10% for 5 min, then 90%
- `Canary10Percent10Minutes` - 10% for 10 min, then 90%
- `Canary10Percent30Minutes` - 10% for 30 min, then 90%
- `Linear10PercentEvery1Minute` - +10% every minute (10 steps)
- `Linear10PercentEvery2Minutes` - +10% every 2 min (20 min total)
- `Linear10PercentEvery3Minutes` - +10% every 3 min (30 min total)
- `Linear10PercentEvery10Minutes` - +10% every 10 min (100 min total)
- `AllAtOnce` - Immediate switch (no canary)

### Alarm Thresholds

Adjust in `template.yaml`:

```yaml
FunctionErrorAlarm:
  Properties:
    Threshold: 5              # Number of errors
    EvaluationPeriods: 2      # Consecutive periods
    Period: 60                # Seconds per period
```

## Troubleshooting

### Deployment Stuck

```bash
# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name bedrock-agentcore-lambda-dev \
  --query 'Stacks[0].StackStatus'

# Check CodeDeploy deployment status
aws deploy get-deployment --deployment-id d-XXXXX
```

### Pre-Traffic Hook Failed

```bash
# Check hook function logs
aws logs tail /aws/lambda/CodeDeployHook_preTraffic_dev --follow

# Common issues:
# - Lambda timeout (increase timeout in template.yaml)
# - IAM permissions missing
# - Test event format incorrect
```

### Alarms Not Triggering Rollback

```bash
# Verify alarm configuration
aws cloudwatch describe-alarms \
  --alarm-names bedrock-agentcore-lambda-dev-errors

# Check alarm history
aws cloudwatch describe-alarm-history \
  --alarm-name bedrock-agentcore-lambda-dev-errors \
  --max-records 10
```

## Best Practices

1. **Always deploy to dev first**
   ```bash
   sam deploy --config-env dev
   # Test thoroughly
   sam deploy --config-env prod
   ```

2. **Monitor during canary window**
   ```bash
   # Open multiple terminals:
   # Terminal 1: Watch logs
   sam logs -n BedrockAgentFunction --tail

   # Terminal 2: Monitor deployment
   watch -n 5 'aws deploy list-deployments --application-name ServerlessDeploymentApplication'

   # Terminal 3: Check CloudWatch alarms
   watch -n 10 'aws cloudwatch describe-alarms --state-value ALARM'
   ```

3. **Test rollback in dev**
   ```bash
   # Deploy intentionally broken code to dev
   # Verify automatic rollback works
   # Practice manual rollback procedures
   ```

4. **Use longer canary for prod**
   ```yaml
   # In template.yaml for production
   DeploymentPreference:
     Type: Canary10Percent30Minutes  # More conservative
   ```

5. **Set up SNS notifications**
   ```yaml
   # Get notified on deployment events
   DeploymentPreference:
     TriggerConfigurations:
       - TriggerEvents:
           - DeploymentFailure
           - DeploymentSuccess
         TriggerTargetArn: !Ref DeploymentTopic
   ```

## Summary

- ✅ **SAM CLI automatically triggers CodeDeploy** - no manual CodeDeploy commands needed
- ✅ **Just run `sam deploy`** - everything else is automatic
- ✅ **Canary deployment happens during CloudFormation update**
- ✅ **Alarms trigger automatic rollback** if issues detected
- ✅ **Manual control available** via AWS CLI for custom A/B tests
- ✅ **Monitor via CloudFormation, CodeDeploy, and Lambda consoles**

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [CodeDeploy for Lambda](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-steps-lambda.html)
- [Lambda Aliases](https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html)
- [SAM Gradual Deployments](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/automating-updates-to-serverless-apps.html)
