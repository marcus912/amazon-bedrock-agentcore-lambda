# Lambda Function Architecture Refactoring Proposal

## Current Problems

1. **God Function**: `lambda_handler` has 180+ lines doing everything
2. **No Type Safety**: Raw dicts, no clear contracts
3. **Mixed Error Handling**: Nested try-except, unclear boundaries
4. **Poor Testability**: Hard to isolate and test components
5. **Unclear Return Policy**: Always deletes messages, even on fatal errors

## Proposed Architecture

### **Layers** (Keep existing + add new)

```
┌─────────────────────────────────────────┐
│   Handler Layer (Orchestration)         │  ← Very thin, just coordinates
├─────────────────────────────────────────┤
│   Domain Layer (Business Logic)         │  ← NEW: Email processing pipeline
├─────────────────────────────────────────┤
│   Services Layer (Utilities)            │  ← Existing: email, s3, prompts
├─────────────────────────────────────────┤
│   Integrations Layer (External APIs)    │  ← Existing: agentcore_invocation
└─────────────────────────────────────────┘
```

### **Key Principles**

1. **Single Responsibility**: Each function does ONE thing
2. **Type Safety**: Use dataclasses for structured data
3. **Result Pattern**: Explicit success/failure handling
4. **Error Boundaries**: Separate recoverable vs fatal errors
5. **Testability**: Easy to mock and test each layer

### **New Structure**

```
src/
├── handlers/
│   └── sqs_email_handler.py       # Thin orchestration (30 lines)
├── domain/                         # NEW: Business logic
│   ├── models.py                   # Data classes
│   ├── email_processor.py          # Email processing pipeline
│   └── result.py                   # Result types
├── services/                       # Existing utilities
│   ├── email.py
│   ├── s3.py
│   └── prompts.py
└── integrations/                   # Existing integrations
    └── agentcore_invocation.py
```

## Detailed Design

### **1. Data Models** (`domain/models.py`)

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class EmailMetadata:
    """Structured email metadata."""
    from_address: str
    to_addresses: List[str]
    subject: str
    timestamp: str
    bucket_name: str
    object_key: str

@dataclass
class EmailContent:
    """Parsed email content."""
    text_body: str
    html_body: str
    attachments: List[dict]

    @property
    def body_for_agent(self) -> str:
        """Get best available body for agent."""
        return self.text_body or self.html_body or ""

@dataclass
class ProcessingResult:
    """Result of email processing."""
    success: bool
    message_id: str
    error_message: Optional[str] = None
    agent_response: Optional[str] = None

    @property
    def should_delete_message(self) -> bool:
        """Always delete to prevent infinite retries."""
        return True  # Policy: always delete, log errors
```

### **2. Email Processor** (`domain/email_processor.py`)

```python
from typing import Dict, Any
import logging
from .models import EmailMetadata, EmailContent, ProcessingResult
from services import email as email_service, s3 as s3_service
from integrations import agentcore_invocation

logger = logging.getLogger(__name__)

class EmailProcessor:
    """Handles end-to-end email processing pipeline."""

    def process_ses_record(self, record: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single SQS record containing SES notification.

        This is the main entry point for processing. It:
        1. Parses the SES notification
        2. Fetches email from S3
        3. Invokes agent to create GitHub issue
        4. Returns result (success or error)

        All errors are caught and logged. Message is always deleted.
        """
        message_id = record.get('messageId', 'UNKNOWN')

        try:
            # Parse notification
            metadata = self._parse_ses_notification(record)
            logger.info(f"Parsed email metadata: {metadata.subject}")

            # Fetch email
            email_content = self._fetch_email(metadata)
            logger.info(f"Fetched email: {len(email_content.body_for_agent)} chars")

            # Process with agent
            agent_response = self._invoke_agent(metadata, email_content)
            logger.info(f"Agent response: {agent_response[:100]}...")

            return ProcessingResult(
                success=True,
                message_id=message_id,
                agent_response=agent_response
            )

        except Exception as e:
            logger.error(f"Processing failed for {message_id}: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                message_id=message_id,
                error_message=str(e)
            )

    def _parse_ses_notification(self, record: Dict[str, Any]) -> EmailMetadata:
        """Parse SQS record and extract SES notification."""
        # Implementation...
        pass

    def _fetch_email(self, metadata: EmailMetadata) -> EmailContent:
        """Fetch and parse email from S3."""
        # Implementation...
        pass

    def _invoke_agent(
        self,
        metadata: EmailMetadata,
        content: EmailContent
    ) -> str:
        """Invoke Bedrock agent to create GitHub issue."""
        # Implementation...
        pass
```

### **3. Thin Handler** (`handlers/sqs_email_handler.py`)

```python
from typing import Dict, Any
import logging
from domain.email_processor import EmailProcessor

logger = logging.getLogger(__name__)

# Initialize processor once (reused across invocations)
processor = EmailProcessor()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for SES email processing.

    Policy: Always delete messages to prevent infinite retries.
    All errors are logged to CloudWatch for manual review.
    """
    logger.info("Processing batch of %d messages", len(event.get('Records', [])))

    results = []
    for record in event.get('Records', []):
        result = processor.process_ses_record(record)
        results.append(result)

        if result.success:
            logger.info(f"✓ Success: {result.message_id}")
        else:
            logger.warning(f"✗ Error: {result.message_id} - {result.error_message}")

    # Always delete all messages (policy decision)
    return {"batchItemFailures": []}
```

## Benefits

### **Before**:
- 180+ line god function
- Hard to test
- Mixed concerns
- No type safety
- Unclear error handling

### **After**:
- 30 line handler (orchestration only)
- Easy to test each component
- Clear separation of concerns
- Type-safe data models
- Explicit error handling with Result pattern

## Migration Strategy

1. Create new `domain/` directory
2. Implement `models.py` (dataclasses)
3. Implement `email_processor.py` (extract logic from handler)
4. Update tests to use new structure
5. Replace old handler with thin version
6. Delete old helper functions (moved to EmailProcessor)

## Testing Strategy

```python
# Old (hard to test)
def test_lambda_handler():
    # Must mock: SQS, SNS, SES, S3, Bedrock, etc.
    # Tightly coupled
    pass

# New (easy to test)
def test_email_processor():
    processor = EmailProcessor()
    result = processor.process_ses_record(mock_record)
    assert result.success

def test_parse_ses_notification():
    metadata = processor._parse_ses_notification(mock_record)
    assert metadata.subject == "Test"
```

## Open Questions

1. **Should we ever NOT delete messages?**
   - Current: Always delete
   - Alternative: Fatal config errors could fail Lambda

2. **Do we need a dead letter queue?**
   - Current: No DLQ, errors just logged
   - Alternative: Send failed messages to DLQ for replay

3. **Should we add metrics?**
   - CloudWatch metrics for success/failure rates
   - Alert on high error rates

## Recommendation

**Implement this refactoring** because:
- ✅ Much easier to maintain
- ✅ Much easier to test
- ✅ Type-safe
- ✅ Clear separation of concerns
- ✅ Easier to add features
