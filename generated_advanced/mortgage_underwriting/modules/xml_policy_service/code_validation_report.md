# Code Validation Report: XML Policy Service

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 72

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/exceptions.py:9:9: W292 no newline at end of file

### models.py
**Warnings:**
- models.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:3:1: F401 'sqlalchemy.orm.relationship' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:4:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:6:1: F401 'sqlalchemy.Numeric' imported but unused

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:6:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:8:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:34:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:60:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:61:101: E501 line too long (101 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:4:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:4:1: F401 'typing.Dict' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:4:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:6:1: F401 'sqlalchemy.text' imported but unused

### routes.py

### schema_model_consistency
**Errors:**
- LenderPolicy: >50% of fields missing in LenderPolicyResponse - check schema/model field name synchronization

