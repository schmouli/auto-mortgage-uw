```json
[
  {
    "title": "Messaging service fails to send email notification due to missing template",
    "description": "The messaging service raises a KeyError when attempting to retrieve an undefined email template during notification dispatch.",
    "test_name": "tests/unit/test_messaging.py::test_send_email_notification_missing_template",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_messaging.py\", line 42, in test_send_email_notification_missing_template\n    await messaging_service.send_email(user_id=123, template_key=\"nonexistent_template\")\n  File \"/workspace/mortgage_underwriting/modules/messaging/services.py\", line 67, in send_email\n    template = self.templates[template_key]\nKeyError: 'nonexistent_template'",
    "error_message": "'nonexistent_template'",
    "affected_code": [
      "modules/messaging/services.py",
      "line 67"
    ],
    "suggested_fix": "Add validation check before accessing templates dictionary; raise custom exception for invalid keys.",
    "severity": "high"
  },
  {
    "title": "Condition evaluation returns incorrect boolean for edge-case income threshold",
    "description": "A condition rule evaluating minimum annual income fails for values near the threshold ($49,999 vs expected $50,000), returning False instead of True.",
    "test_name": "tests/unit/test_conditions.py::test_condition_min_income_edge_case",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_conditions.py\", line 88, in test_condition_min_income_edge_case\n    assert evaluate_condition(\"min_annual_income\", 49999.99) is True\nAssertionError",
    "error_message": "assert False is True",
    "affected_code": [
      "modules/conditions/services.py",
      "line 112"
    ],
    "suggested_fix": "Adjust comparison logic from strict '>' to '>=' for inclusive thresholds.",
    "severity": "high"
  },
  {
    "title": "Messaging route does not sanitize user-provided subject line input",
    "description": "User-submitted subject lines containing script tags are reflected directly in response without sanitization, posing XSS risk.",
    "test_name": "tests/integration/test_messaging_integration.py::test_send_email_subject_xss",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/integration/test_messaging_integration.py\", line 56, in test_send_email_subject_xss\n    assert '<script>' not in response.json()['subject']\nAssertionError",
    "error_message": "assert '<script>' not in '<script>alert(1)</script>'",
    "affected_code": [
      "modules/messaging/routes.py",
      "line 31"
    ],
    "suggested_fix": "Sanitize all user inputs using HTML escape utilities before storing or reflecting them.",
    "severity": "high"
  },
  {
    "title": "Conditions engine fails to handle nullified conditional dependencies gracefully",
    "description": "When upstream dependency data is None, downstream conditions throw AttributeError instead of defaulting or skipping.",
    "test_name": "tests/unit/test_conditions.py::test_null_dependency_handling",
    "error_type": "AttributeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_conditions.py\", line 105, in test_null_dependency_handling\n    result = evaluate_condition_tree(tree_with_null_deps)\n  File \"/workspace/mortgage_underwriting/modules/conditions/services.py\", line 203, in evaluate_condition_tree\n    outcome = node.condition.evaluate(data)\n  File \"/workspace/mortgage_underwriting/modules/conditions/models.py\", line 91, in evaluate\n    return self.logic_fn(dependency_value)\n  File \"/workspace/mortgage_underwriting/modules/conditions/logic.py\", line 24, in greater_than_threshold\n    return value > self.threshold\nAttributeError: 'NoneType' object has no attribute '__gt__'",
    "error_message": "'NoneType' object has no attribute '__gt__'",
    "affected_code": [
      "modules/conditions/logic.py",
      "line 24"
    ],
    "suggested_fix": "Wrap evaluations in try-except blocks or validate presence of required dependencies prior to execution.",
    "severity": "medium"
  }
]
```