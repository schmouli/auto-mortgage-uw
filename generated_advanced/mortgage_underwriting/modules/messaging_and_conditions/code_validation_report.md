# Code Validation Report: Messaging & Conditions

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 95

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:29:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:35:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:36:45: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:17:101: E501 line too long (135 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:18:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:19:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:22:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:24:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:24:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:56:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:61:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:81:15: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 87.5% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:9:1: F401 'mortgage_underwriting.modules.messaging_conditions.schemas.MessageUpdateRead' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:32:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:33:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:37:1: W293 blank line contains whitespace

### routes.py

### schema_model_consistency
**Errors:**
- Message: >50% of fields missing in MessageResponse - check schema/model field name synchronization
- Condition: >50% of fields missing in ConditionResponse - check schema/model field name synchronization

