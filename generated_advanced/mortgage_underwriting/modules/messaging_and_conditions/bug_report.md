```json
[
  {
    "title": "Condition evaluation fails for null effective_date",
    "description": "The condition evaluator raises a TypeError when effective_date is None due to naive datetime comparison.",
    "test_name": "tests/unit/test_conditions_evaluator.py::test_condition_with_null_effective_date",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/conditions/services.py\", line 72, in evaluate_condition\n    if condition.effective_date <= now:\nTypeError: '<=' not supported between instances of 'NoneType' and 'datetime.datetime'",
    "error_message": "TypeError: '<=' not supported between instances of 'NoneType' and 'datetime.datetime'",
    "affected_code": [
      "mortgage_underwriting/modules/conditions/services.py",
      "line 72"
    ],
    "suggested_fix": "Add null check before comparing dates: `if condition.effective_date and condition.effective_date <= now:`",
    "severity": "high"
  },
  {
    "title": "Messaging service sends unencrypted PII in email subject line",
    "description": "During message templating, borrower SIN was included directly in email subject causing PIPEDA violation.",
    "test_name": "tests/integration/test_messaging_integration.py::test_send_notification_contains_pii_in_subject",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/messaging/services.py\", line 105, in send_notification\n    msg['Subject'] = template.render(title=title)\n  File \"<template>\", line 1, in top-level template code\njinja2.exceptions.UndefinedError: 'sin' is undefined\n\nDuring handling of the above exception, borrower.sin was manually inserted into subject.\n\n  File \"/app/tests/integration/test_messaging_integration.py\", line 88, in test_send_notification_contains_pii_in_subject\n    assert '[REDACTED]' in sent_email.subject\nAssertionError: assert '[REDACTED]' in 'Loan Update - John Doe (***-***-*** SIN)'",
    "error_message": "assert '[REDACTED]' in 'Loan Update - John Doe (***-***-*** SIN)'",
    "affected_code": [
      "mortgage_underwriting/modules/messaging/services.py",
      "line 105"
    ],
    "suggested_fix": "Implement strict sanitization filter on all template inputs and enforce masking via middleware before rendering subjects.",
    "severity": "critical"
  },
  {
    "title": "Condition rule engine ignores inactive conditions",
    "description": "Inactive conditions with status != 'active' are still being evaluated during underwriting process.",
    "test_name": "tests/unit/test_conditions_engine.py::test_inactive_condition_not_evaluated",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/conditions/services.py\", line 48, in apply_conditions\n    result = evaluate_condition(condition)\n  File \"/app/mortgage_underwriting/modules/conditions/services.py\", line 75, in evaluate_condition\n    raise ConditionNotMetError(f\"Condition {condition.id} not met\")\n  File \"/app/tests/unit/test_conditions_engine.py\", line 62, in test_inactive_condition_not_evaluated\n    assert len(results) == 0\nAssertionError: assert 1 == 0",
    "error_message": "assert 1 == 0",
    "affected_code": [
      "mortgage_underwriting/modules/conditions/services.py",
      "lines 45-48"
    ],
    "suggested_fix": "Filter out inactive conditions before evaluation loop: `conditions = [c for c in conditions if c.status == 'active']`",
    "severity": "high"
  },
  {
    "title": "Messaging audit log omits recipient identifier",
    "description": "Audit logs do not store recipient identifiers, violating FINTRAC traceability requirements for messaging events.",
    "test_name": "tests/unit/test_messaging_audit.py::test_message_event_logs_recipient",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/messaging/models.py\", line 32, in log_message_event\n    audit_entry['recipient_id'] = message.recipient.id\nKeyError: 'recipient_id'\n\nDuring handling of the above exception, structlog logged partial entry without recipient tracking.\n\n  File \"/app/tests/unit/test_messaging_audit.py\", line 44, in test_message_event_logs_recipient\n    assert 'recipient_id' in logged_fields\nAssertionError",
    "error_message": "KeyError: 'recipient_id'",
    "affected_code": [
      "mortgage_underwriting/modules/messaging/models.py",
      "line 32"
    ],
    "suggested_fix": "Ensure recipient ID is always mapped from message object prior to logging; fallback to external_id if internal user missing.",
    "severity": "medium"
  }
]
```