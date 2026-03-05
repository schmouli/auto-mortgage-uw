BLOCKED: Gate 1 failed
- File: tests/unit_tests.py, line 1
  Issue: Missing module-level docstring explaining purpose of test file
  Fix: Add docstring at top of file

BLOCKED: Gate 3 failed
- File: tests/unit_tests.py, line 115
  Issue: Bare `except:` clause in `test_compliance_check_gds_tds_limits` 
  Fix: Specify exception type (e.g., `except ValidationError:` or appropriate custom exception)

BLOCKED: Gate 4 failed
- File: tests/conftest.py, line 1
  Issue: Missing module-level docstring
  Fix: Add explanatory docstring for conftest.py

BLOCKED: Gate 6 failed
- File: tests/integration_tests.py, line 1
  Issue: Missing module-level docstring
  Fix: Add docstring describing integration test scope

Additional Issues:
- File: tests/unit_tests.py, function `test_compliance_check_gds_tds_limits`
  Issue: Mock data lacks required fields to compute GDS/TDS (missing `heating`, `monthly_debt`, etc.)
  Risk: Test does not accurately simulate OSFI B-20 GDS/TDS calculation logic

⚠️ WARNING: Several test functions reference undefined models (`Application`, `Report`) and schemas (`ReportType`) which may cause runtime failures during execution. Ensure all referenced components exist in their respective modules.