#!/bin/bash
# Upload prompts to S3
# Usage: bin/update-prompts.sh [env] [prompt-file]
#        bin/update-prompts.sh                      # Interactive - prompts for environment
#        bin/update-prompts.sh dev                  # Upload all prompts to dev
#        bin/update-prompts.sh qa                   # Upload all prompts to qa
#        bin/update-prompts.sh all                  # Upload all prompts to ALL environments
#        bin/update-prompts.sh prod github_issue.txt  # Upload specific prompt to prod

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ALL_ENVIRONMENTS="dev qa prod"

# Check if environment argument provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Select environment to upload prompts:${NC}"
    echo "   1) dev"
    echo "   2) qa"
    echo "   3) prod"
    echo "   4) all"
    echo ""
    read -p "Enter choice (1-4) or environment name: " choice

    case "$choice" in
        1|dev)   ENVIRONMENT="dev" ;;
        2|qa)    ENVIRONMENT="qa" ;;
        3|prod)  ENVIRONMENT="prod" ;;
        4|all)   ENVIRONMENT="all" ;;
        *)
            echo -e "${RED}❌ Invalid choice: $choice${NC}"
            exit 1
            ;;
    esac
    PROMPT_FILE=""
else
    # Parse arguments
    # First arg: environment (dev, qa, prod, all)
    # Second arg: specific prompt file (optional)
    ENVIRONMENT="$1"

    # Validate environment
    if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod|all)$ ]]; then
        # If first arg is not an env, treat it as a prompt file (backward compat)
        if [ -f "src/prompts/$1" ]; then
            PROMPT_FILE="$1"
            ENVIRONMENT="dev"
        else
            echo -e "${RED}❌ Error: Invalid environment '$ENVIRONMENT'${NC}"
            echo "   Valid environments: dev, qa, prod, all"
            exit 1
        fi
    else
        PROMPT_FILE="$2"
    fi
fi

# Save selected environment before loading .env
SELECTED_ENV="$ENVIRONMENT"

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

# Restore selected environment (may have been overwritten by .env)
ENVIRONMENT="$SELECTED_ENV"

# Configuration
S3_BUCKET="${STORAGE_BUCKET_NAME}"
PROMPTS_DIR="src/prompts/"

# Validate bucket name
if [ -z "$S3_BUCKET" ]; then
    echo -e "${RED}❌ Error: STORAGE_BUCKET_NAME not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration loaded:${NC}"
if [ "$ENVIRONMENT" = "all" ]; then
    echo "   Environments: $ALL_ENVIRONMENTS"
else
    echo "   Environment: $ENVIRONMENT"
fi
echo "   S3 Bucket: $S3_BUCKET"
echo "   Local Dir: $PROMPTS_DIR"
echo ""

# Check if prompts directory exists
if [ ! -d "$PROMPTS_DIR" ]; then
    echo -e "${RED}❌ Error: $PROMPTS_DIR directory not found${NC}"
    exit 1
fi

# Function to upload a single prompt to a specific environment
upload_prompt_to_env() {
    local file=$1
    local env=$2
    local filename=$(basename "$file")
    local s3_key="prompts/${env}/${filename}"

    echo -e "${GREEN}📤 Uploading: ${filename} -> ${env}${NC}"
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

# Function to upload prompts to one or all environments
upload_prompts() {
    local envs_to_upload="$1"
    local specific_file="$2"

    for env in $envs_to_upload; do
        echo -e "${GREEN}🚀 Uploading to ${env}...${NC}"
        echo ""

        if [ -n "$specific_file" ]; then
            # Upload specific prompt
            upload_prompt_to_env "$specific_file" "$env"
            echo ""
        else
            # Upload all prompts
            PROMPT_COUNT=0
            for file in ${PROMPTS_DIR}*.txt; do
                if [ -f "$file" ]; then
                    upload_prompt_to_env "$file" "$env"
                    echo ""
                    PROMPT_COUNT=$((PROMPT_COUNT + 1))
                fi
            done

            if [ $PROMPT_COUNT -eq 0 ]; then
                echo -e "${YELLOW}⚠️  No .txt files found in $PROMPTS_DIR${NC}"
                exit 1
            fi
        fi
    done
}

# Upload prompts
if [ -n "$PROMPT_FILE" ]; then
    # Upload specific prompt
    PROMPT_PATH="${PROMPTS_DIR}${PROMPT_FILE}"

    if [ ! -f "$PROMPT_PATH" ]; then
        echo -e "${RED}❌ Error: Prompt file not found: $PROMPT_PATH${NC}"
        exit 1
    fi

    if [ "$ENVIRONMENT" = "all" ]; then
        upload_prompts "$ALL_ENVIRONMENTS" "$PROMPT_PATH"
    else
        upload_prompts "$ENVIRONMENT" "$PROMPT_PATH"
    fi
else
    # Upload all prompts
    if [ "$ENVIRONMENT" = "all" ]; then
        upload_prompts "$ALL_ENVIRONMENTS" ""
    else
        upload_prompts "$ENVIRONMENT" ""
    fi
fi

echo ""
echo -e "${GREEN}✅ Prompt upload complete!${NC}"
echo ""
echo -e "${YELLOW}📋 View uploaded prompts:${NC}"
if [ "$ENVIRONMENT" = "all" ]; then
    echo "   aws s3 ls s3://${S3_BUCKET}/prompts/ --recursive"
else
    echo "   aws s3 ls s3://${S3_BUCKET}/prompts/${ENVIRONMENT}/"
fi
echo ""
echo -e "${YELLOW}📥 Download a prompt:${NC}"
if [ "$ENVIRONMENT" = "all" ]; then
    echo "   aws s3 cp s3://${S3_BUCKET}/prompts/dev/github_issue.txt -"
else
    echo "   aws s3 cp s3://${S3_BUCKET}/prompts/${ENVIRONMENT}/github_issue.txt -"
fi
