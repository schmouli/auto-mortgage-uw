# Code Validation Report: Lender Comparison & Submission

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 100

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/exceptions.py:19:74: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:28:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:33:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:34:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:37:101: E501 line too long (117 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:38:101: E501 line too long (126 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:41:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:105:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:145:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:158:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:159:101: E501 line too long (104 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:10:101: E501 line too long (117 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:31:55: E712 comparison to True should be 'if cond is True:' or 'if cond:'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:37:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:43:41: E712 comparison to True should be 'if cond is True:' or 'if cond:'

### routes.py
**Warnings:**
- Type hints missing in routes.py::list_lenders: missing return type
- Type hints missing in routes.py::get_lender_products: missing return type
- Type hints missing in routes.py::match_lenders: missing return type
- Type hints missing in routes.py::create_submission: missing return type
- Type hints missing in routes.py::list_submissions: missing return type

### schema_model_consistency
**Errors:**
- Lender: >50% of fields missing in LenderResponse - check schema/model field name synchronization
- LenderProduct: >50% of fields missing in LenderProductResponse - check schema/model field name synchronization
- LenderSubmission: >50% of fields missing in LenderSubmissionResponse - check schema/model field name synchronization

