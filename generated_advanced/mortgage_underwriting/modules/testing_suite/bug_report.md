```json
[
  {
    "title": "Missing Indexes on Frequently Queried Columns",
    "description": "Detected lack of database indexes on commonly filtered/query columns such as email, foreign key fields, and status enums. This will lead to performance degradation under load.",
    "test_name": "N/A (static analysis)",
    "error_type": "PerformanceWarning",
    "stack_trace": "",
    "error_message": "No index found on column 'email' in table users; similar issue for FKs like applicant_id",
    "affected_code": ["models.py", "multiple tables"],
    "suggested_fix": "Add indexes using sqlalchemy.Index or index=True parameter in Column definitions for high-cardinality and frequently queried fields",
    "severity": "high"
  },
  {
    "title": "List Endpoints Lack Pagination",
    "description": "All list endpoints should enforce pagination with skip/limit parameters and a maximum page size of 100 records to prevent excessive memory usage and denial-of-service risks.",
    "test_name": "N/A (API contract review)",
    "error_type": "Security/ScalabilityIssue",
    "stack_trace": "",
    "error_message": "Endpoint /applicants returns full dataset without limit, posing scalability and DoS risk",
    "affected_code": ["routes.py", "services.py"],
    "suggested_fix": "Implement query(skip, limit) with server-side enforced max limit=100",
    "severity": "high"
  },
  {
    "title": "Potential SQL Injection Vector Detected",
    "description": "Raw string interpolation used in SQL queries instead of parameterized statements. High-risk vulnerability allowing malicious input execution.",
    "test_name": "N/A (code inspection)",
    "error_type": "SecurityViolation",
    "stack_trace": "",
    "error_message": "String formatting detected in raw SQL: f'SELECT * FROM loans WHERE status = {status}'",
    "affected_code": ["services.py", "line 72"],
    "suggested_fix": "Refactor to use SQLAlchemy Core or ORM methods exclusively, avoiding manual SQL concatenation",
    "severity": "high"
  },
  {
    "title": "Foreign Keys Missing OnDelete Behavior Specification",
    "description": "Several ForeignKey constraints do not define an ON DELETE policy which may cause orphaned rows or cascade failures during deletions.",
    "test_name": "N/A (schema validation)",
    "error_type": "DataIntegrityError",
    "stack_trace": "",
    "error_message": "ForeignKey('applicant.id') is missing ondelete='CASCADE' or other explicit behavior",
    "affected_code": ["models.py", "multiple model relationships"],
    "suggested_fix": "Explicitly set onDelete policies: e.g., ForeignKey('table.id', ondelete='CASCADE')",
    "severity": "high"
  },
  {
    "title": "Public Functions Missing Type Hints",
    "description": "Type hinting is inconsistent across service layer functions. Required by project standards for clarity, tooling support, and correctness.",
    "test_name": "N/A (linting/mypy check)",
    "error_type": "CodeQualityIssue",
    "stack_trace": "",
    "error_message": "Function calculate_gds has no return type annotation",
    "affected_code": ["services.py", "various functions"],
    "suggested_fix": "Annotate all public functions with proper type hints per PEP 484",
    "severity": "high"
  }
]
```