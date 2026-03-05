BLOCKED: Gate 1 failed  
- File: mortgage_underwriting/modules/document_management/services.py, line 42  
  Issue: Function `upload_document` missing return type hint  
  Fix: Add `-> Document`  

BLOCKED: Gate 3 failed  
- File: mortgage_underwriting/modules/document_management/services.py, line 58  
  Issue: Bare `except:` clause used in virus scan handling  
  Fix: Replace with explicit exception type, e.g., `except VirusScanError as e:`  

BLOCKED: Gate 4 failed  
- File: mortgage_underwriting/modules/document_management/services.py, line 61  
  Issue: Using `print()` instead of structured logging  
  Fix: Replace with `logger.error("virus_detected", exc_info=True)`  

BLOCKED: Gate 6 failed  
- File: mortgage_underwriting/modules/document_management/services.py, line 75  
  Issue: Public method `update_document_status` lacks docstring  
  Fix: Add docstring describing purpose, args, return value, and exceptions  

BLOCKED: Gate 6 failed  
- File: mortgage_underwriting/modules/document_management/routes.py, line 30  
  Issue: Endpoint handler `update_document_status_endpoint` missing docstring  
  Fix: Add docstring explaining request/response behavior and possible errors  

⚠️ WARNING: Unable to validate full compliance due to partial code provided. Please supply all relevant source files (`models.py`, `schemas.py`, `services.py`, `routes.py`) for complete assessment.