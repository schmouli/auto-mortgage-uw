```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/infrastructure/models.py, line 23
  Issue: `details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)` — Field may store PII (e.g., stack traces or system info), violating PIPEDA. Must encrypt or sanitize before storage.
  Fix: Add encryption using `common/security.encrypt_pii()` or enforce sanitization/logging restrictions.

- File: mortgage_underwriting/modules/infrastructure/models.py, line 44
  Issue: `logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)` — Potentially contains sensitive deployment logs which may include paths, IPs, or internal configs.
  Fix: Encrypt field or restrict content; never log sensitive data.

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/infrastructure/services.py, line 32
  Issue: `logger.error("service_health_creation_failed", error=str(e))` — Exposes raw exception messages that could contain sensitive context.
  Fix: Log generic message and use `exc_info=True` for stack trace visibility without exposing data.

- File: mortgage_underwriting/modules/infrastructure/services.py, line 70
  Issue: `logger.error("deployment_trigger_failed", error=str(e))` — Same as above; risk of leaking infra details.
  Fix: Sanitize error logging.

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/infrastructure/models.py
  Issue: Missing docstrings for model classes (`ServiceHealth`, `Deployment`, `InfrastructureConfig`)
  Fix: Add one-line descriptions in class docstrings per documentation standards.

⚠️ NOTE: Regulatory Compliance
- OSFI B-20, FINTRAC, CMHC, PIPEDA do not apply directly to this module (non-mortgage logic). However, general security and privacy practices still apply.
```