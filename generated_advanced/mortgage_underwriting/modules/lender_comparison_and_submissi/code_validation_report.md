# Code Validation Report: Lender Comparison & Submission

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 72

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:17:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:22:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:23:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:26:101: E501 line too long (130 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:27:101: E501 line too long (109 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:30:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:77:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:112:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:129:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:131:101: E501 line too long (101 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 87.5% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:11:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:11:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:11:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderProductCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:11:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderProductUpdate' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:74:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:89:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:106:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:135:10: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- Lender: >50% of fields missing in LenderResponse - check schema/model field name synchronization
- LenderProduct: >50% of fields missing in LenderProductResponse - check schema/model field name synchronization
- LenderSubmission: >50% of fields missing in LenderSubmissionResponse - check schema/model field name synchronization

