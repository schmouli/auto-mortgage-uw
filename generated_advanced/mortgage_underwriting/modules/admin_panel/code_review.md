```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 9,
      "description": "Broken import statement causes syntax error. Import block is split across lines breaking Python syntax.",
      "suggested_fix": "Fix import statement structure:\n```python\nfrom .schemas import (\n    UserListResponse,\n    UserDeactivateRequest,\n    UserDeactivateResponse,\n    UserRoleChangeRequest,\n    UserRoleChangeResponse,\n    LenderCreate,\n    LenderUpdate,\n    LenderProductCreate,\n    LenderProductUpdate\n)\nfrom sqlalchemy import select, func as sql_func\n```"
    },
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/admin_panel/routes.py",
      "line": 5,
      "description": "Broken import statement causes syntax error. Import block is split across lines breaking Python syntax.",
      "suggested_fix": "Fix import statement structure:\n```python\nfrom .schemas import (\n    UserListResponse,\n    UserDeactivateRequest,\n    UserDeactivateResponse,\n    UserRoleChangeRequest,\n    UserRoleChangeResponse,\n    LenderCreate,\n    LenderUpdate,\n    LenderProductCreate,\n    LenderProductUpdate,\n    AuditLogResponse\n)\nfrom .services import AdminService\n```"
    },
    {
      "severity": "critical",
      "category": "database",
      "file": "mortgage_underwriting/modules/admin_panel/models.py",
      "line": 25,
      "description": "Missing updated_at audit field. All models must include both created_at and updated_at according to project conventions.",
      "suggested_fix": "Add updated_at field:\n```python\nupdated_at: Mapped[datetime] = mapped_column(\n    DateTime(timezone=True), \n    server_default=func.now(), \n    onupdate=func.now(), \n    nullable=False\n)\n```"
    },
    {
      "severity": "critical",
      "category": "security",
      "file": "mortgage_underwriting/modules/admin_panel/routes.py",
      "line": 24,
      "description": "No rate limiting on admin endpoints. Admin endpoints are high-value targets for brute force attacks and must have rate limiting.",
      "suggested_fix": "Add rate limiting to all admin endpoints:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.get('/users')\n@limiter.limit('10/minute')\nasync def list_users(request: Request, ...):\n    ...\n```"
    },
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/admin_panel/routes.py",
      "line": 35,
      "description": "Bare except clause catches all exceptions including critical failures. Violates 'NEVER use bare except' rule.",
      "suggested_fix": "Catch specific exceptions:\n```python\nfrom mortgage_underwriting.common.exceptions import AppException\n\ntry:\n    return await service.list_users(...)\nexcept AppException as e:\n    raise HTTPException(status_code=400, detail={'detail': str(e), 'error_code': 'ADMIN_ERROR'})\nexcept Exception as e:\n    logger.error('unexpected_error', error=str(e))\n    raise HTTPException(status_code=500, detail={'detail': 'Internal server error', 'error_code': 'INTERNAL_ERROR'})\n```"
    },
    {
      "severity": "critical",
      "category": "database",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 85,
      "description": "Double commit without transaction management. User update and audit log should be atomic. If second commit fails, user is deactivated without audit trail.",
      "suggested_fix": "Use single transaction:\n```python\nasync with self.db.begin():\n    user.is_active = False\n    await self.db.flush()\n    audit_entry = AuditLog(...)\n    self.db.add(audit_entry)\n# Commit happens automatically on context exit\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 67,
      "description": "Fragile name splitting logic. Parsing first_name/last_name from full_name is error-prone for names with multiple parts, single names, or empty values.",
      "suggested_fix": "Store first_name and last_name separately in User model or use a robust parsing library. Alternatively, return full_name and let client handle splitting:\n```python\n# In schema, add full_name field and deprecate first_name/last_name\nfull_name: Optional[str]\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/admin_panel/models.py",
      "line": 17,
      "description": "Missing index on action column. The get_audit_logs method frequently filters by action but no index exists, causing full table scans.",
      "suggested_fix": "Add index to action column:\n```python\naction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 115,
      "description": "No validation that lender exists before creating product. Foreign key constraint will fail at database level but should be validated early for better error messages.",
      "suggested_fix": "Add validation:\n```python\nasync def add_product(self, payload: LenderProductCreate) -> LenderProduct:\n    # Verify lender exists\n    lender_stmt = select(Lender).where(Lender.id == payload.lender_id)\n    lender_result = await self.db.execute(lender_stmt)\n    if not lender_result.scalar_one_or_none():\n        raise AppException('Lender not found')\n    # Proceed with creation\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "security",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 78,
      "description": "Audit log missing ip_address and user_agent despite model having these fields. FINTRAC requires comprehensive audit trails including client metadata.",
      "suggested_fix": "Pass request metadata to service:\n```python\n# In routes.py, capture request info\nasync def deactivate_user(..., request: Request):\n    ip_address = request.client.host\n    user_agent = request.headers.get('user-agent')\n    return await service.deactivate_user(..., ip_address, user_agent)\n\n# In services.py\nasync def deactivate_user(..., ip_address: Optional[str], user_agent: Optional[str]):\n    audit_entry = AuditLog(..., ip_address=ip_address, user_agent=user_agent)\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/admin_panel/schemas.py",
      "line": 68,
      "description": "LenderProductUpdate inherits from LenderProductCreate making all fields required. Update schemas should have optional fields.",
      "suggested_fix": "Use base class with optional fields for updates:\n```python\nclass LenderProductBase(BaseModel):\n    lender_id: int\n    product_name: str\n    # ... other fields\n\nclass LenderProductCreate(LenderProductBase):\n    pass\n\nclass LenderProductUpdate(BaseModel):\n    lender_id: Optional[int] = None\n    product_name: Optional[str] = None\n    # ... other fields optional\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 12,
      "description": "Tests use SQLite instead of PostgreSQL. Project uses PostgreSQL 15 with specific features (JSONB, arrays, etc.). Tests will not catch database-specific issues.",
      "suggested_fix": "Use PostgreSQL test container:\n```python\nfrom testcontainers.postgres import PostgresContainer\n\n@pytest.fixture(scope='session')\ndef postgres():\n    with PostgresContainer('postgres:15') as postgres:\n        yield postgres\n\n@pytest.fixture\ndef db_session(postgres):\n    TEST_DATABASE_URL = postgres.get_connection_url().replace('postgresql', 'postgresql+asyncpg')\n    # ... rest of setup\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 42,
      "description": "No pytest markers on fixtures or tests. Project requires @pytest.mark.unit and @pytest.mark.integration for test categorization.",
      "suggested_fix": "Add markers to test files:\n```python\n@pytest.mark.unit\nasync def test_list_users():\n    ...\n\n@pytest.mark.integration\nasync def test_create_lender_integration(db_session):\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 48,
      "description": "No ORDER BY clause in queries. Pagination results are non-deterministic and can return different results on each call.",
      "suggested_fix": "Add ordering:\n```python\nstmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 9,
      "description": "Unused import 'update' from sqlalchemy. Clean up unused imports to reduce confusion.",
      "suggested_fix": "Remove unused import:\n```python\nfrom sqlalchemy import select, func as sql_func\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/admin_panel/exceptions.py",
      "line": 1,
      "description": "AdminException does not inherit from AppException. Breaks consistent error handling across modules.",
      "suggested_fix": "Inherit from base exception:\n```python\nfrom mortgage_underwriting.common.exceptions import AppException\n\nclass AdminException(AppException):\n    '''Base exception for admin panel operations.'''\n    pass\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 155,
      "description": "[TRUNCATED CODE WARNING] Cannot fully validate get_audit_logs implementation. Code appears to be incomplete based on truncation marker.",
      "suggested_fix": "Provide complete code for full validation. Ensure proper pagination, filtering, and eager loading implementation."
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/admin_panel/routes.py",
      "line": 112,
      "description": "Unused path parameter lender_id in update_product and deactivate_product endpoints. Parameter is not validated against product's actual lender.",
      "suggested_fix": "Either remove parameter or validate it:\n```python\nif product.lender_id != lender_id:\n    raise HTTPException(status_code=400, detail='Product does not belong to lender')\n```"
    },
    {
      "severity": "medium",
      "category": "security",
      "file": "mortgage_underwriting/modules/admin_panel/routes.py",
      "line": 98,
      "description": "Mutating request payload object directly. Bad practice that can cause side effects and makes code harder to reason about.",
      "suggested_fix": "Create new dictionary instead:\n```python\ndata = payload.model_dump()\ndata['lender_id'] = lender_id\nproduct = LenderProduct(**data)\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/admin_panel/schemas.py",
      "line": 11,
      "description": "Role and status as free strings instead of enums. Prone to typos and lacks type safety.",
      "suggested_fix": "Use StrEnum:\n```python\nfrom enum import StrEnum\n\nclass UserRole(StrEnum):\n    ADMIN = 'admin'\n    UNDERWRITER = 'underwriter'\n    READ_ONLY = 'read_only'\n\nclass UserStatus(StrEnum):\n    ACTIVE = 'active'\n    INACTIVE = 'inactive'\n    PENDING = 'pending'\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/admin_panel/services.py",
      "line": 52,
      "description": "Magic strings 'active'/'inactive' used directly. Should use constants.",
      "suggested_fix": "Define constants:\n```python\nUSER_STATUS_ACTIVE = 'active'\nUSER_STATUS_INACTIVE = 'inactive'\n```"
    }
  ],
  "summary": "CRITICAL BLOCKING ISSUES: Syntax errors in import statements break the module completely. Missing rate limiting, transaction management, and proper error handling create security and data integrity risks. HIGH SEVERITY: Fragile name parsing, missing database indexes, incomplete audit logging, and inadequate test infrastructure. The module requires immediate fixes before deployment. FINTRAC compliance gaps in audit trails and PIPEDA considerations for logging need thorough review."
}
```