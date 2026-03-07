# Code Validation Report: Background Jobs (Celery + Redis)

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 86

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/exceptions.py:9:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:11:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:25:101: E501 line too long (112 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:26:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/models.py:35:101: E501 line too long (115 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:10:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:24:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:32:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/schemas.py:34:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:4:1: F401 'typing.Dict' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:4:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/services.py:4:1: F401 'typing.List' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:4:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:6:1: F401 'fastapi.Query' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/background_jobs_(celery_+_redi/routes.py:17:101: E501 line too long (107 > 100 characters)

### schema_model_consistency
**Errors:**
- JobExecutionLog: >50% of fields missing in JobExecutionLogResponse - check schema/model field name synchronization
- ScheduledJob: >50% of fields missing in ScheduledJobResponse - check schema/model field name synchronization

