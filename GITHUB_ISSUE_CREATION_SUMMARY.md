# GitHub Issue Creation from Customer Emails - Summary

## What Was Changed

The SQS email handler Lambda function has been updated to automatically create GitHub bug issues from customer support emails using a Bedrock AI agent with GitHub MCP (Model Context Protocol) tools and knowledge base integration.

**Important**: The Lambda function does NOT create GitHub issues itself. The Bedrock agent uses its built-in GitHub MCP tools to create issues directly.

## Key Changes

### 1. **Updated Email Processing Flow** (`src/sqs_email_handler.py`)

**Before**:
- Email → Parse → Summarize → Log

**After**:
- Email → Parse → **AI Agent with Knowledge Base** → **Agent Creates GitHub Issue via MCP** → **Log Confirmation** → Done

### 2. **New Functions Added**

#### `create_github_issue_prompt()` (Lines 261-320)
Generates the AI agent prompt with:
- Customer email details
- **Step-by-step instructions with knowledge base query FIRST**
- **Validation for missing required fields**
- **Error handling for missing template**
- **Instructions to use GitHub MCP tools to create the issue**
- **Configurable repository parameter** (default: "bugs")
- Expected response format (confirmation with URL)

#### `log_email_processing()` (Lines 196-256)
Logs the processed email and agent response:
- Records email metadata (subject, from, to, timestamp)
- Logs email body content preview
- **Logs agent's confirmation message with GitHub issue URL**
- No parsing or GitHub API calls (agent handles everything)

### 3. **Updated Process Flow**

The `lambda_handler` now:
1. Fetches email from S3
2. Parses MIME content
3. **Creates prompt instructing agent to use GitHub MCP tools**
4. **Invokes AI agent** (agent queries knowledge base and creates GitHub issue)
5. **Logs agent's confirmation response** with GitHub issue URL
6. Returns processing results

## The AI Agent Prompt

### Purpose
The prompt instructs the AI agent to:
1. **Query the knowledge base FIRST** for bug report templates (with error handling if missing)
2. **Extract key information** from the customer email based on template structure
3. **Validate that required fields** are present in the email (error if critical fields missing)
4. **Format the issue body** according to the retrieved template
5. **Apply appropriate labels** from knowledge base
6. **Use GitHub MCP tools** to create the GitHub issue in configurable repository
7. **Return confirmation** with the GitHub issue URL

### Full Prompt Template

```text
You are a technical support AI agent that creates GitHub bug issues from customer support emails.

**TASK**: Analyze the following customer email and create a GitHub bug issue using your GitHub MCP tools.

**CUSTOMER EMAIL**:
From: {from_address}
Subject: {subject}
Received: {timestamp}

Email Content:
{body}

**INSTRUCTIONS**:
1. FIRST: Query your knowledge base for "github-bug-issue-template" to get the required structure and fields
   - Identify what fields are required (e.g., steps to reproduce, expected behavior, actual behavior, environment details, etc.)
   - If the template is not found in your knowledge base, respond with an error message indicating the template is missing
2. Extract the corresponding information from the customer email to populate those required fields
3. Validate that the email contains sufficient information:
   - If critical required fields are missing from the email, respond with an error message listing which fields could not be extracted
   - Include what information was found and what is missing
4. Format the GitHub issue body according to the template structure you retrieved
5. Apply standard labels and categories as defined in your knowledge base
6. Use your GitHub MCP tools to create the issue in the "{repository}" repository
7. After creating the issue, respond with:
   - Confirmation that the issue was created
   - The GitHub issue URL
   - A brief summary of the issue

**KNOWLEDGE BASE LOOKUP**:
- Search term: "github-bug-issue-template"
- This template defines the structure, required fields, and formatting guidelines
- Reference examples of well-formatted GitHub issues from your knowledge base

Please create the GitHub issue now using your MCP tools and confirm the result.
```

## Knowledge Base Requirements

For optimal results, the AI agent's knowledge base should include:

### 1. **Bug Report Template**
```markdown
## Description
Brief description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Product:
- Version:
- Platform:
- Additional details:
```

### 2. **Severity Classification Guide**
- **Critical (P0)**: System crash, data loss, security breach, service down
- **High (P1)**: Major feature broken, significant performance issue
- **Medium (P2)**: Feature partially working, workaround available
- **Low (P3)**: Minor issue, cosmetic problem, enhancement request

### 3. **Product Catalog**
- List of all products and components
- Standard labels for each product line
- Component categorization

### 4. **Example Issues**
- Well-formatted GitHub issue examples
- Various severity levels
- Different product categories

## How to Configure the Knowledge Base

### Step 1: Prepare Documents

Create these files in your knowledge base:

**`bug-report-template.md`**
```markdown
# Bug Report Template

Use this template for all customer-reported bugs.

## Required Sections
[template content here]
```

**`severity-guide.md`**
```markdown
# Severity Classification

## Critical (P0)
- System crashes or hangs
- Data loss or corruption
...
```

**`product-catalog.md`**
```markdown
# Product Catalog

## Routers
- Linksys XYZ Router
  - Components: network, wifi, firmware
  - Labels: product-router, component-network
...
```

**`example-issues.md`**
```markdown
# Example GitHub Issues

## Example 1: Critical Bug
Title: Bug: Router crashes under high load
Body: ...
Labels: bug, severity-critical, component-network
...
```

### Step 2: Upload to Bedrock Knowledge Base

```bash
# Using AWS CLI
aws bedrock-agent create-knowledge-base \
  --name "support-bug-templates" \
  --description "Templates and guides for bug report creation" \
  --role-arn "arn:aws:iam::799870512242:role/BedrockKnowledgeBaseRole"

# Upload documents
aws bedrock-agent create-data-source \
  --knowledge-base-id "your-kb-id" \
  --name "bug-templates" \
  --data-source-configuration '{
    "type": "S3",
    "s3Configuration": {
      "bucketArn": "arn:aws:s3:::your-kb-bucket"
    }
  }'
```

### Step 3: Associate with Agent

Link the knowledge base to your Bedrock agent:
```bash
aws bedrock-agent associate-agent-knowledge-base \
  --agent-id "your-agent-id" \
  --knowledge-base-id "your-kb-id" \
  --description "Bug report templates and guidelines"
```

## Testing the Integration

### Test Email Example

Send an email to your SES address:

```
From: test@example.com
Subject: Bug: App freezes when syncing large files
To: support@yourdomain.com

Hi Support,

I'm having a serious issue with the mobile app. Whenever I try to sync files
larger than 50MB, the app completely freezes and I have to force quit.

This happens on:
- iPhone 14 Pro
- iOS 17.2
- App version 3.1.2

Steps:
1. Open the app
2. Go to sync settings
3. Enable "Sync All"
4. App freezes during sync of large files

Please fix this ASAP, it's blocking my work!

Thanks,
John Doe
```

### Expected Agent Response

```
GitHub issue created successfully!

Issue URL: https://github.com/owner/repository/issues/789

Summary:
- Title: Bug: Mobile app freezes when syncing files over 50MB
- Severity: High
- Labels: bug, customer-reported, severity-high, component-sync, platform-ios
- Reporter: test@example.com
- Created: 2025-11-14T10:30:00Z

The issue has been created with complete details:
- App freezes during large file sync (>50MB)
- Steps to reproduce: Open app → Sync settings → Enable 'Sync All' → Freeze
- Environment: iOS 17.2, iPhone 14 Pro, App v3.1.2
- Impact: Blocking user's workflow - high priority
- User must force quit to recover

The development team has been notified.
```

### Check CloudWatch Logs

```bash
# View logs
aws logs tail /aws/lambda/ses-email-handler-dev --follow

# Look for:
# - "Invoking Bedrock agent to create GitHub issue from email..."
# - "AGENT RESPONSE (GitHub issue created by agent):"
# - "Issue URL: https://github.com/..."
# - "NOTE: GitHub issue creation is handled by the agent's MCP tools"
```

Example log output:
```
AGENT RESPONSE (GitHub issue created by agent):
----------------------------------------------------------------------
GitHub issue created successfully!

Issue URL: https://github.com/owner/repository/issues/789

Summary:
- Title: Bug: Mobile app freezes when syncing files over 50MB
- Severity: High
...
----------------------------------------------------------------------
NOTE: GitHub issue creation is handled by the agent's MCP tools
```

## Benefits of This Approach

1. **Automated Triage**: AI classifies severity and priority automatically
2. **Consistent Format**: All issues follow the same template structure
3. **Knowledge-Based**: Leverages organizational knowledge for better categorization
4. **Robust Validation**: Checks for template availability and required fields before creating issues
5. **Better Error Handling**: Clear error messages when template is missing or email lacks critical information
6. **Time Savings**: Eliminates manual issue creation from emails
7. **Improved Quality**: Extracts all relevant details from customer emails
8. **Scalable**: Handles high volume of support emails
9. **Flexible**: Configurable target repository per use case
10. **Traceable**: Full audit trail in CloudWatch Logs
11. **Simplified Architecture**: No GitHub credentials or API code in Lambda - agent handles everything via MCP
12. **Reduced Maintenance**: No GitHub library dependencies to manage or update
13. **Secure**: GitHub access is managed at the agent level, not in application code

## Monitoring and Metrics

### CloudWatch Metrics to Track

1. **Agent Invocation Success Rate**
2. **GitHub Issue Creation Success Rate** (from agent responses)
3. **Processing Time per Email**
4. **Severity Distribution** (critical/high/medium/low)
5. **Email Volume and Processing Rate**

### CloudWatch Alarms

Set up alarms for:
- Agent invocation failures > 5%
- Agent error responses > 10%
- Processing time > 30 seconds
- Email backlog growing

## Next Steps

1. **Configure Agent's GitHub MCP Tools**: Ensure agent has GitHub repository access
2. **Test with Sample Emails**: Send various bug reports to test classification
3. **Refine Knowledge Base**: Add more examples and templates
4. **Monitor Results**: Track issue quality and agent accuracy in CloudWatch logs
5. **Iterate**: Improve prompts based on agent performance
6. **Set Up Notifications**: Alert team when critical issues are created

## Additional Documentation

- Full prompt details: `AGENT_PROMPT.md`
- Code implementation: `src/sqs_email_handler.py`
- Test suite: `tests/test_sqs_email_handler.py`
