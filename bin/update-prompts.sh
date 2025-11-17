#!/bin/bash
# Upload prompts to S3
# Usage: bin/update-prompts.sh [prompt-file]
#        bin/update-prompts.sh              # Upload all prompts
#        bin/update-prompts.sh github_issue.txt  # Upload specific prompt

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
    exit 1
fi

# Load environment variables
echo -e "${GREEN}📦 Loading configuration from .env...${NC}"
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Configuration
S3_BUCKET="${SES_EMAIL_BUCKET_NAME}"
S3_PREFIX="prompts/"
PROMPTS_DIR="src/prompts/"

# Validate bucket name
if [ -z "$S3_BUCKET" ]; then
    echo -e "${RED}❌ Error: SES_EMAIL_BUCKET_NAME not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration loaded:${NC}"
echo "   S3 Bucket: $S3_BUCKET"
echo "   S3 Prefix: $S3_PREFIX"
echo "   Local Dir: $PROMPTS_DIR"
echo ""

# Check if prompts directory exists
if [ ! -d "$PROMPTS_DIR" ]; then
    echo -e "${RED}❌ Error: $PROMPTS_DIR directory not found${NC}"
    exit 1
fi

# Function to upload a single prompt
upload_prompt() {
    local file=$1
    local filename=$(basename "$file")
    local s3_key="${S3_PREFIX}${filename}"

    echo -e "${GREEN}📤 Uploading: ${filename}${NC}"
    echo "   Local:  $file"
    echo "   S3:     s3://${S3_BUCKET}/${s3_key}"

    aws s3 cp "$file" "s3://${S3_BUCKET}/${s3_key}" \
        --region us-west-2 \
        --content-type "text/plain"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✅ Uploaded successfully${NC}"
    else
        echo -e "${RED}   ❌ Upload failed${NC}"
        return 1
    fi
}

# Upload prompts
if [ -n "$1" ]; then
    # Upload specific prompt
    PROMPT_FILE="${PROMPTS_DIR}$1"

    if [ ! -f "$PROMPT_FILE" ]; then
        echo -e "${RED}❌ Error: Prompt file not found: $PROMPT_FILE${NC}"
        exit 1
    fi

    upload_prompt "$PROMPT_FILE"
else
    # Upload all prompts
    echo -e "${GREEN}🚀 Uploading all prompts...${NC}"
    echo ""

    PROMPT_COUNT=0
    for file in ${PROMPTS_DIR}*.txt; do
        if [ -f "$file" ]; then
            upload_prompt "$file"
            echo ""
            PROMPT_COUNT=$((PROMPT_COUNT + 1))
        fi
    done

    if [ $PROMPT_COUNT -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No .txt files found in $PROMPTS_DIR${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✅ Prompt upload complete!${NC}"
echo ""
echo -e "${YELLOW}📋 View uploaded prompts:${NC}"
echo "   aws s3 ls s3://${S3_BUCKET}/${S3_PREFIX}"
echo ""
echo -e "${YELLOW}📥 Download a prompt:${NC}"
echo "   aws s3 cp s3://${S3_BUCKET}/${S3_PREFIX}github_issue.txt -"
echo ""
echo -e "${YELLOW}🔄 List versions (if versioning enabled):${NC}"
echo "   aws s3api list-object-versions --bucket ${S3_BUCKET} --prefix ${S3_PREFIX}"
