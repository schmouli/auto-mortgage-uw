# Code Validation Report: Messaging & Conditions

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 92

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 77.8%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:7:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:3:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:4:1: F401 'sqlalchemy.dialects.postgresql.UUID' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:19:101: E501 line too long (126 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:15:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:18:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:21:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 77.77777777777779% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:7:1: F401 'sqlalchemy.orm.selectinload' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:12:1: F401 'mortgage_underwriting.modules.messaging.schemas.MessageUpdateRead' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:12:101: E501 line too long (132 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:4:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:20:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:20:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:35:1: E302 expected 2 blank lines, found 1

