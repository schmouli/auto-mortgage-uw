# Code Validation Report: Background Jobs (Celery + Redis)

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 85

## Type Coverage

- exceptions.py: 0.0%
- models.py: 100%
- schemas.py: 100%
- services.py: 83.3%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:19:46: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:3:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:15:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:23:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:24:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:9:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:14:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:24:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:37:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:5:1: F401 'typing.Dict' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:5:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:11:1: F401 'mortgage_underwriting.modules.jobs.schemas.ScheduledJobCreate' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:6:1: F401 'fastapi.Query' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:26:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:35:13: F821 undefined name 'NotFoundError'

