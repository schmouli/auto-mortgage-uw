```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 13
  Issue: Missing type annotation for mapped column `id` in ServiceHealth
  Fix: Annotate as Mapped[int]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 14
  Issue: Missing type annotation for mapped column `service_name` in ServiceHealth
  Fix: Annotate as Mapped[str]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 15
  Issue: Missing type annotation for mapped column `status` in ServiceHealth
  Fix: Annotate as Mapped[str]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 16
  Issue: Missing type annotation for mapped column `details` in ServiceHealth
  Fix: Annotate as Mapped[Optional[Dict[str, Any]]]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 17
  Issue: Missing type annotation for mapped column `checked_at` in ServiceHealth
  Fix: Annotate as Mapped[datetime]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 18
  Issue: Missing type annotation for mapped column `created_at` in ServiceHealth
  Fix: Annotate as Mapped[datetime]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 19
  Issue: Missing type annotation for mapped column `updated_at` in ServiceHealth
  Fix: Annotate as Mapped[datetime]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 27
  Issue: Missing type annotation for mapped column `id` in SystemStatus
  Fix: Annotate as Mapped[int]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 28
  Issue: Missing type annotation for mapped column `overall_status` in SystemStatus
  Fix: Annotate as Mapped[str]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 29
  Issue: Missing type annotation for mapped column `service_statuses` in SystemStatus
  Fix: Annotate as Mapped[Dict[str, Any]]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 30
  Issue: Missing type annotation for mapped column `gpu_status` in SystemStatus
  Fix: Annotate as Mapped[Optional[Dict[str, Any]]]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 31
  Issue: Missing type annotation for mapped column `recorded_at` in SystemStatus
  Fix: Annotate as Mapped[datetime]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 32
  Issue: Missing type annotation for mapped column `created_at` in SystemStatus
  Fix: Annotate as Mapped[datetime]

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure_deployment/models.py, line 33
  Issue: Missing type annotation for mapped column `updated_at` in SystemStatus
  Fix: Annotate as Mapped[datetime]
```