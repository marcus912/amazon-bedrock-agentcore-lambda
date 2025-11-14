# AI Agent Prompt for GitHub Issue Creation

## Overview

This document contains the prompt template used to invoke the Bedrock AI agent for analyzing customer bug reports from emails and creating GitHub issues using the agent's built-in GitHub MCP (Model Context Protocol) tools.

## Architecture

The Lambda function invokes the Bedrock agent with a customer email, and the agent:
1. Analyzes the email content
2. Queries its knowledge base for bug report templates
3. **Uses its GitHub MCP tools to create the issue directly**
4. Returns a confirmation with the issue URL

**Note**: The Lambda function does NOT create GitHub issues itself. The agent handles all GitHub interactions via MCP tools.

## Prompt Template

The Lambda function uses the following prompt structure when invoking the AI agent:

```
You are a technical support AI agent that creates GitHub bug issues from customer support emails.

**TASK**: Analyze the following customer email and create a GitHub bug issue using your GitHub MCP tools.

**CUSTOMER EMAIL**:
From: {from_address}
Subject: {subject}
Received: {timestamp}

Email Content:
{body}

**INSTRUCTIONS**:
1. Refer to your knowledge base for the bug report template and standard formatting
2. Extract key information from the customer email:
   - Error messages, stack traces, or symptoms
   - Affected product/component
   - Reproduction steps if mentioned
   - Environment details (firmware versions, model numbers, etc.)
   - Any workarounds or attempted fixes

3. Determine severity based on impact:
   - Critical: System crash, data loss, security breach, service down
   - High: Major feature broken, significant performance issue
   - Medium: Feature partially working, workaround available
   - Low: Minor issue, cosmetic problem

4. Use your GitHub MCP tools to create a bug issue with:
   - Title: Brief, descriptive title (50-80 chars)
   - Body: Detailed description following the knowledge base template
   - Labels: Include bug, customer-reported, severity level, and component
   - Include reporter email ({from_address}) and report date ({timestamp}) in the issue body

5. After creating the issue, respond with:
   - Confirmation that the issue was created
   - The GitHub issue URL
   - A brief summary of the issue

**KNOWLEDGE BASE LOOKUP**:
- Search for "bug report template" to structure the issue body
- Reference examples of well-formatted GitHub issues
- Use standard labels and categories from your knowledge base

Please create the GitHub issue now using your MCP tools and confirm the result.
```

## Dynamic Variables

The prompt template includes the following dynamic variables that are populated from the incoming email:

- `{from_address}`: Customer's email address
- `{subject}`: Email subject line
- `{timestamp}`: When the email was received
- `{body}`: Full email body content

## Expected Agent Response

The agent uses its GitHub MCP tools to create the issue and returns a confirmation message:

```
GitHub issue created successfully!

Issue URL: https://github.com/owner/repository/issues/123

Summary:
- Title: Bug: Router crashes when handling 100+ concurrent connections
- Severity: High
- Labels: bug, customer-reported, severity-high, component-network, product-router
- Reporter: customer@example.com
- Created: 2025-11-14T10:30:00Z

The issue has been formatted according to the bug report template and includes:
- Detailed description of the crash behavior
- Steps to reproduce with 100+ concurrent connections
- Environment details (Linksys Router XYZ, Firmware 1.2.3.4)
- Expected vs actual behavior comparison
```

## Knowledge Base Requirements

For this prompt to work effectively, the AI agent's knowledge base should contain:

### 1. Bug Report Template

A standard template for formatting bug reports, including:
- Description section
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Severity classification guidelines

### 2. Product Information

- List of products and components
- Version naming conventions
- Standard labels for each product line

### 3. Severity Classification Guide

Clear criteria for determining severity levels:
- **Critical**: System crashes, data loss, security vulnerabilities
- **High**: Major feature broken, significant performance degradation
- **Medium**: Feature partially working, workaround available
- **Low**: Minor issue, cosmetic problems

### 4. Example GitHub Issues

Well-formatted examples of GitHub issues for reference, showing:
- Proper title formatting
- Complete bug descriptions
- Appropriate use of labels
- Priority assignment

## Implementation Notes

### Code Location

The prompt generation is handled by the `create_github_issue_prompt()` function in:
- File: `src/sqs_email_handler.py`
- Lines: 261-325

### Agent Invocation

The Lambda function invokes the agent using:
- File: `src/integrations/agentcore_invocation.py`
- Function: `invoke_agent(prompt, session_id)`
- The agent handles all GitHub interactions via its MCP tools
- No GitHub API code exists in the Lambda function

### Response Handling

The agent's response (including the GitHub issue URL) is logged by:
- Function: `log_email_processing()`
- File: `src/sqs_email_handler.py`
- Lines: 196-256
- Logs the agent's confirmation message to CloudWatch for monitoring

## Testing the Prompt

### Sample Customer Email

```
From: customer@example.com
Subject: Bug: App crashes when uploading files over 10MB
Received: 2025-11-14T10:30:00Z

Email Content:
Hi Support Team,

I'm experiencing a critical issue with the mobile app (v2.5.1).
Every time I try to upload a file larger than 10MB, the app crashes immediately.

Steps to reproduce:
1. Open the app
2. Navigate to upload section
3. Select a file over 10MB
4. App crashes with error "Memory allocation failed"

I'm using:
- iPhone 14
- iOS 17.2
- App version 2.5.1

This is blocking my work. Please help!

Thanks,
John
```

### Expected AI Agent Output

```
GitHub issue created successfully!

Issue URL: https://github.com/owner/repository/issues/456

Summary:
- Title: Bug: Mobile app crashes when uploading files over 10MB
- Severity: Critical
- Labels: bug, customer-reported, severity-critical, component-upload, platform-ios
- Reporter: customer@example.com
- Created: 2025-11-14T10:30:00Z

The issue has been created with the following details:
- Complete description of the memory allocation failure
- Steps to reproduce (open app → upload section → select 10MB+ file → crash)
- Environment: iOS 17.2, iPhone 14, App v2.5.1
- Impact: Blocking customer's work - critical priority
- Error message: 'Memory allocation failed'

The issue is ready for the development team to review.
```

## Deployment Configuration

### Environment Variables Required

Add these to your Lambda environment (in `template.yaml` or `.env`):

```bash
# Required - already configured
AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:799870512242:runtime/linksys_email_agent-5D3liLGRtN

# Note: No GitHub credentials needed in Lambda
# The Bedrock agent uses its own GitHub MCP tools for issue creation
```

### Knowledge Base Setup

Ensure the Bedrock agent has access to a knowledge base containing:
1. Upload bug report template documents
2. Upload product catalog and component list
3. Upload severity classification guide
4. Upload example GitHub issues

## Usage Flow

1. **Email Received** → SES stores in S3, sends notification to SQS
2. **Lambda Triggered** → Reads email from S3, parses MIME content
3. **Prompt Created** → Calls `create_github_issue_prompt()` with email data
4. **Agent Invoked** → Bedrock agent analyzes email using knowledge base
5. **Agent Creates Issue** → Agent uses its GitHub MCP tools to create the GitHub issue
6. **Agent Returns Confirmation** → Agent responds with issue URL and summary
7. **Log Result** → Success/failure and agent response logged to CloudWatch

## Monitoring

Check CloudWatch Logs for:
- Agent invocation success/failure
- Agent responses with GitHub issue URLs
- Email processing results
- Any error messages from the agent

Log group: `/aws/lambda/ses-email-handler-{environment}`

Example log output:
```
AGENT RESPONSE (GitHub issue created by agent):
GitHub issue created successfully!
Issue URL: https://github.com/owner/repository/issues/456
...
NOTE: GitHub issue creation is handled by the agent's MCP tools
```

## Future Enhancements

1. **Smart Priority Assignment**: Use ML to predict priority based on historical data
2. **Duplicate Detection**: Check for similar existing issues before creating new ones
3. **Auto-Assignment**: Route issues to appropriate team members based on component
4. **Customer Notification**: Send confirmation email when issue is created
5. **Metrics Dashboard**: Track issue creation rate, categories, resolution time
