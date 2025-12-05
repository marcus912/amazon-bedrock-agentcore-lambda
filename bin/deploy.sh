#!/bin/bash
# SAM Stack Deployment Script
# Deploys ALL Lambda functions in the stack (reads config from .env)
# Usage: ./deploy.sh
#        ENVIRONMENT=staging ./deploy.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo -e "${YELLOW}💡 Create one from the example:${NC}"
    echo "   cp .env.example .env"
    echo "   # Edit .env with your actual AWS resource identifiers"
    exit 1
fi

# Load environment variables
echo -e "${GREEN}📦 Loading configuration from .env...${NC}"
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Validate required variables
REQUIRED_VARS=("ENVIRONMENT" "AGENT_RUNTIME_ARN" "SES_EMAIL_BUCKET_NAME" "SQS_QUEUE_ARN")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Error: Missing required variables in .env:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

# Set defaults for optional variables
BEDROCK_READ_TIMEOUT=${BEDROCK_READ_TIMEOUT:-300}

# Display configuration
echo -e "${GREEN}✅ Configuration loaded:${NC}"
echo "   Environment: $ENVIRONMENT"
echo "   Agent ARN: ${AGENT_RUNTIME_ARN:0:50}..."
echo "   S3 Bucket: $SES_EMAIL_BUCKET_NAME"
echo "   SQS Queue: ${SQS_QUEUE_ARN:0:50}..."
echo "   Bedrock Timeout: ${BEDROCK_READ_TIMEOUT}s"
echo ""

# Build
echo -e "${GREEN}🔨 Building SAM stack (all Lambda functions)...${NC}"
sam build

# Deploy
echo -e "${GREEN}🚀 Deploying entire stack to AWS ($ENVIRONMENT)...${NC}"
sam deploy \
  --config-env "$ENVIRONMENT" \
  --parameter-overrides \
    "Environment=$ENVIRONMENT" \
    "AgentRuntimeArn=$AGENT_RUNTIME_ARN" \
    "SESEmailBucketName=$SES_EMAIL_BUCKET_NAME" \
    "SQSQueueArn=$SQS_QUEUE_ARN" \
    "BedrockReadTimeout=$BEDROCK_READ_TIMEOUT"

echo ""
echo -e "${GREEN}✅ Stack deployment complete!${NC}"
echo -e "${YELLOW}📊 View Lambda function logs:${NC}"
echo "   aws logs tail /aws/lambda/sqs-email-handler-$ENVIRONMENT --follow"
echo ""
echo -e "${YELLOW}📋 List deployed functions:${NC}"
echo "   aws cloudformation describe-stack-resources --stack-name bedrock-agentcore-lambda-$ENVIRONMENT --query 'StackResources[?ResourceType==\`AWS::Lambda::Function\`].[LogicalResourceId,PhysicalResourceId]' --output table"
