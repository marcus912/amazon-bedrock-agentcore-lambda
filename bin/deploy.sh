#!/bin/bash
# SAM Stack Deployment Script
# Deploys ALL Lambda functions in the stack (reads config from env file)
# Usage: ./deploy.sh dev          # Deploy to dev (uses .env.dev or .env)
#        ./deploy.sh qa           # Deploy to qa (uses .env.qa)
#        ./deploy.sh prod         # Deploy to prod (uses .env.prod)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if environment argument provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Select environment to deploy:${NC}"
    echo "   1) dev"
    echo "   2) qa"
    echo "   3) prod"
    echo ""
    read -p "Enter choice (1-3) or environment name: " choice

    case "$choice" in
        1|dev)   ENVIRONMENT="dev" ;;
        2|qa)    ENVIRONMENT="qa" ;;
        3|prod)  ENVIRONMENT="prod" ;;
        *)
            echo -e "${RED}❌ Invalid choice: $choice${NC}"
            exit 1
            ;;
    esac
else
    ENVIRONMENT="$1"
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod)$ ]]; then
    echo -e "${RED}❌ Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "   Valid environments: dev, qa, prod"
    exit 1
fi

# Determine env file: .env.{env} or .env for dev
if [ "$ENVIRONMENT" = "dev" ] && [ -f ".env" ] && [ ! -f ".env.dev" ]; then
    ENV_FILE=".env"
else
    ENV_FILE=".env.${ENVIRONMENT}"
fi

# Check if env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: $ENV_FILE file not found${NC}"
    echo -e "${YELLOW}💡 Create one from the example:${NC}"
    echo "   cp .env.example $ENV_FILE"
    echo "   # Edit $ENV_FILE with your actual AWS resource identifiers"
    exit 1
fi

# Load environment variables from file
echo -e "${GREEN}📦 Loading configuration from $ENV_FILE...${NC}"
export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)

# Override ENVIRONMENT with command line argument (ensures consistency)
export ENVIRONMENT

# Validate required variables (ENVIRONMENT already set from arg)
REQUIRED_VARS=("AGENT_RUNTIME_ARN" "SES_EMAIL_BUCKET_NAME" "SQS_QUEUE_ARN")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Error: Missing required variables in $ENV_FILE:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

# Set defaults for optional variables
BEDROCK_READ_TIMEOUT=${BEDROCK_READ_TIMEOUT:-300}
ATTACHMENTS_S3_BUCKET=${ATTACHMENTS_S3_BUCKET:-""}
ATTACHMENTS_CLOUDFRONT_DOMAIN=${ATTACHMENTS_CLOUDFRONT_DOMAIN:-""}
ATTACHMENT_MAX_SIZE_MB=${ATTACHMENT_MAX_SIZE_MB:-20}
AGENT_RUNTIME_POLICY_RESOURCE=${AGENT_RUNTIME_POLICY_RESOURCE:-""}

# Display configuration
echo -e "${GREEN}✅ Configuration loaded:${NC}"
echo "   Environment: $ENVIRONMENT"
echo "   Agent ARN: ${AGENT_RUNTIME_ARN:0:50}..."
echo "   S3 Bucket: $SES_EMAIL_BUCKET_NAME"
echo "   SQS Queue: ${SQS_QUEUE_ARN:0:50}..."
echo "   Bedrock Timeout: ${BEDROCK_READ_TIMEOUT}s"
if [ -n "$ATTACHMENTS_S3_BUCKET" ]; then
    echo "   Attachments Bucket: $ATTACHMENTS_S3_BUCKET"
    echo "   CloudFront Domain: $ATTACHMENTS_CLOUDFRONT_DOMAIN"
    echo "   Max Attachment Size: ${ATTACHMENT_MAX_SIZE_MB} MB"
fi
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
    "AgentRuntimePolicyResource=$AGENT_RUNTIME_POLICY_RESOURCE" \
    "SESEmailBucketName=$SES_EMAIL_BUCKET_NAME" \
    "SQSQueueArn=$SQS_QUEUE_ARN" \
    "BedrockReadTimeout=$BEDROCK_READ_TIMEOUT" \
    "AttachmentsS3Bucket=$ATTACHMENTS_S3_BUCKET" \
    "AttachmentsCloudFrontDomain=$ATTACHMENTS_CLOUDFRONT_DOMAIN" \
    "AttachmentMaxSizeMB=$ATTACHMENT_MAX_SIZE_MB"

echo ""
echo -e "${GREEN}✅ Stack deployment complete!${NC}"
echo -e "${YELLOW}📊 View Lambda function logs:${NC}"
echo "   aws logs tail /aws/lambda/sqs-email-handler-$ENVIRONMENT --follow"
echo ""
echo -e "${YELLOW}📋 List deployed functions:${NC}"
echo "   aws cloudformation describe-stack-resources --stack-name bedrock-agentcore-lambda-$ENVIRONMENT --query 'StackResources[?ResourceType==\`AWS::Lambda::Function\`].[LogicalResourceId,PhysicalResourceId]' --output table"
