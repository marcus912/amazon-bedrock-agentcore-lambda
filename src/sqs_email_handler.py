"""
AWS Lambda handler for processing SES email notifications from SQS.

Thin orchestration layer that delegates to EmailProcessor.
Policy: Always delete messages (no retries). Errors logged to CloudWatch.
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
    Process SES email notifications from SQS.

    Args:
        event: Lambda event with SQS records
        context: Lambda context

    Returns:
        Dict with batchItemFailures (always empty - no retries)
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

    return {"batchItemFailures": []}
