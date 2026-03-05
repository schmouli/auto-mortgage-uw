```
❌ No pytest output found
❌ Please run tester agent first to generate test logs
```

> **Note**: The input does not contain any actual test results or failure logs for the "Document Management" module. To proceed with bug logging, I need structured pytest output showing **failed tests**, **assertion errors**, **tracebacks**, etc.

Please re-run tests and provide the output in one of these formats:
- `pytest --tb=short` or `--tb=line` (preferred)
- Full traceback from CI logs
- Copy-paste terminal output containing FAILED entries like:
  ```
  FAILED tests/unit/test_document_manager.py::test_upload_invalid_file_type - AssertionError: ...
  ```