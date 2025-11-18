"""
AWS Lambda handler for processing SES email notifications from SQS.

This is a thin orchestration layer that delegates all business logic
to the EmailProcessor domain class. The handler's only responsibilities are:
1. Initialize the processor
2. Iterate over SQS records
3. Invoke the processor for each record
4. Log results
5. Return SQS batch response

Architecture:
    Handler (this file) → EmailProcessor → Services → Integrations

Policy:
    Always delete all SQS messages to prevent infinite retries.
    Failed messages are logged to CloudWatch for manual review.
"""

import logging
from typing import Dict, Any

from domain.email_processor import EmailProcessor

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add console handler for local testing (AWS Lambda provides handlers automatically)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Initialize processor once at module level (reused across invocations)
email_processor = EmailProcessor()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for SES email processing.

    This handler processes SQS records containing SES email notifications.
    Each email is processed independently, and the Bedrock agent creates
    GitHub issues using its MCP tools.

    Policy: Always delete all messages (return empty batchItemFailures)
    to prevent infinite retries. Failed messages are logged to CloudWatch.

    Args:
        event: Lambda event containing SQS records
        context: Lambda context object

    Returns:
        Dict with batchItemFailures (always empty)
    """
    logger.info("=" * 70)
    logger.info("SES Email Processor - Started")
    logger.info("=" * 70)

    records = event.get('Records', [])
    logger.info(f"Processing batch of {len(records)} message(s)")

    # Process each record
    results = []
    for record in records:
        result = email_processor.process_ses_record(record)
        results.append(result)

        # Log outcome
        if result.success:
            logger.info(f"✓ Successfully processed message {result.message_id}")
        else:
            logger.warning(
                f"⚠ Processed message {result.message_id} with ERRORS: "
                f"{result.error_message}"
            )

    # Log summary
    logger.info("=" * 70)
    logger.info(f"Batch processing complete: {len(results)} message(s)")
    success_count = sum(1 for r in results if r.success)
    error_count = len(results) - success_count
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info("=" * 70)

    # Policy: Always delete all messages to prevent infinite retries
    # Failed messages are logged to CloudWatch for manual review
    return {"batchItemFailures": []}
