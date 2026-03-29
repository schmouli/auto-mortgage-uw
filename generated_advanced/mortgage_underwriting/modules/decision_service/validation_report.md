```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/decision/models.py, line 28
  Issue: Column `policy_flags` uses `List[str]` which is not supported by SQLAlchemy ORM without explicit type mapping
  Fix: Use `Mapped[List[str]]` with proper JSON type annotation or use `JSON` column with explicit serialization

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/decision/models.py, line 29
  Issue: Column `exceptions` uses `List[Dict[str, Any]]` which is not directly supported by SQLAlchemy ORM
  Fix: Use `Mapped[List[dict]]` or serialize/deserialize manually with JSON column

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/decision/models.py, line 30
  Issue: Column `audit_trail` uses `Dict[str, Any]` which requires manual handling in SQLAlchemy
  Fix: Use `Mapped[dict]` or ensure proper JSON serialization/deserialization

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/decision/services.py, line 105
  Issue: Bare `except Exception as e:` catches all exceptions silently
  Fix: Catch specific exceptions like `AppException`, `CalculationError`, etc., and log appropriately

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/decision/routes.py, line 34
  Issue: Generic `except Exception as e:` used in route handler
  Fix: Handle specific expected exceptions and return structured error responses

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/decision/services.py, line 107
  Issue: Logs contain floating point conversion of Decimal values (`gds=float(gds)`)
  Fix: Keep Decimal types in logs; do not convert to float to avoid precision loss

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/decision/services.py, lines 47-60
  Issue: Complex mortgage payment calculation lacks inline documentation explaining formula purpose
  Fix: Add explanatory comments detailing each step of the financial computation for auditability

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/decision/services.py, line 78
  Issue: Hard-coded regulatory thresholds (39%, 44%, 95%) without named constants
  Fix: Define constants such as `MAX_GDS_RATIO = Decimal('39')` for clarity and maintainability
```