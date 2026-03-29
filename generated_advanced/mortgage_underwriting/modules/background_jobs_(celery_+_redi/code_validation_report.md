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
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:5:39: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:16:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:24:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:25:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:39:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:40:101: E501 line too long (101 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:41:52: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 66.66666666666666% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:11:101: E501 line too long (142 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:22:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:24:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:28:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:8:101: E501 line too long (122 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:14:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:25:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:27:9: F821 undefined name 'logger'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:28:101: E501 line too long (154 > 100 characters)

