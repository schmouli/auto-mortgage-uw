# Code Validation Report: Background Jobs (Celery + Redis)

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 20

## Type Coverage

- exceptions.py: 100%
- models.py: 0.0%
- schemas.py: 100%
- services.py: 85.7%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:31:9: W292 no newline at end of file

### models.py
**Warnings:**
- models.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:26:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:28:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:29:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:30:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:33:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:46:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:54:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 85.71428571428571% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:9:1: F401 'mortgage_underwriting.common.exceptions.AppException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:12:1: F401 'mortgage_underwriting.modules.background_jobs.exceptions.JobNotFoundError' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:57:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:60:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:8:1: F401 'mortgage_underwriting.modules.background_jobs.exceptions.JobNotFoundError' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:101:84: W292 no newline at end of file

