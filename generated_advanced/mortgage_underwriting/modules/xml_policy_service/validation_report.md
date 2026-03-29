```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/policy/models.py, line 37
  Issue: Missing type annotation for relationship field `evaluations` (Mapped[list["PolicyEvaluation"]])
  Fix: Add proper Mapped type hint with string-literal reference

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/policy/models.py, line 54
  Issue: Missing type annotation for relationship field `policy` (Mapped["LenderPolicy"])
  Fix: Add proper Mapped type hint with string-literal reference

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/policy/services.py, line 84
  Issue: Using float() to parse XML values from policy rules (e.g., gds_limit = float(...))
  Fix: Replace float with Decimal for all financial calculations; update schema/data handling accordingly

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/policy/services.py, line 89
  Issue: Logs may include PII through application_data contents in details field
  Fix: Sanitize or remove sensitive fields before logging; ensure no DOB, SIN, income exposed

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/policy/services.py, lines 79-91
  Issue: Complex business logic lacks inline documentation of the XML parsing and evaluation process
  Fix: Add detailed docstrings/comments explaining how policy evaluation works and what elements are expected in XML

BLOCKED: Gate 2 failed
- File: mortgage_underwriting/modules/policy/routes.py, line 8
  Issue: Import statement split across two lines unnecessarily
  Fix: Consolidate imports into a single clean block

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/policy/routes.py, multiple places
  Issue: Generic except Exception clauses without distinguishing underlying causes
  Fix: Handle specific exceptions like InvalidXMLFormatError, PolicyNotFoundError explicitly where applicable
```