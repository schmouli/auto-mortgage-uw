# Code Validation Report: Background Jobs (Celery + Redis)

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 35

## Type Coverage

- exceptions.py: 0.0%
- models.py: 100%
- schemas.py: 100%
- services.py: 66.7%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:13:62: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:13:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:26:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:27:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:28:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:32:101: E501 line too long (144 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:10:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:15:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:16:101: E501 line too long (152 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:23:101: E501 line too long (143 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:34:16: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 66.66666666666666% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:1:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:9:101: E501 line too long (127 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:26:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:27:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:7:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:23:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:33:54: W292 no newline at end of file

