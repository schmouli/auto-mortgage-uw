```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "database",
      "file": "mortgage_underwriting/modules/policy/models.py",
      "line": 34,
      "description": "PolicyEvaluation.policy_id missing ForeignKey constraint, violating referential integrity and FINTRAC audit trail requirements",
      "suggested_fix": "Add ForeignKey constraint:\n```python\npolicy_id: Mapped[int] = mapped_column(Integer, ForeignKey(\"lender_policies.id\"), nullable=False)\n```"
    },
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/routes.py",
      "line": 7,
      "description": "Broken import syntax - imports are split across lines causing invalid Python syntax",
      "suggested_fix": "Reorder imports correctly:\n```python\nfrom mortgage_underwriting.modules.policy.schemas import (\n    LenderPolicyCreate,\n    LenderPolicyUpdate,\n    LenderPolicyResponse,\n    PolicyEvaluationRequest,\n    PolicyEvaluationResponse,\n    PolicyListResponse\n)\nfrom mortgage_underwriting.modules.policy.services import PolicyService\n```"
    },
    {
      "severity": "critical",
      "category": "security",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 3,
      "description": "Using xml.etree.ElementTree is vulnerable to XML bomb attacks (Billion Laughs, external entity expansion)",
      "suggested_fix": "Replace with defusedxml:\n```python\n# uv add defusedxml\nfrom defusedxml import ElementTree as ET\n```"
    },
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 115,
      "description": "Using float for GDS/TDS limits violates NEVER use float for money rule and causes precision loss",
      "suggested_fix": "Use Decimal for all financial values:\n```python\nfrom decimal import Decimal\ngds_limit = Decimal(root.find('.//GDS').attrib['max'])\ntds_limit = Decimal(root.find('.//TDS').attrib['max'])\n```"
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 113,
      "description": "OSFI B-20 compliance violation - no stress test applied (qualifying_rate = max(contract_rate + 2%, 5.25%)) and hard limits GDS ≤ 39%, TDS ≤ 44% not enforced",
      "suggested_fix": "Implement OSFI stress test logic:\n```python\ncontract_rate = Decimal(str(payload.application_data.get('interest_rate', 0)))\nqualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))\n# Apply stress test to payment calculations\ngds_limit = Decimal('0.39')\ntds_limit = Decimal('0.44')\n# Log full calculation breakdown for audit\nlogger.info(\"osfi_stress_test_calculation\", qualifying_rate=qualifying_rate, gds_limit=gds_limit, tds_limit=tds_limit)\n```"
    },
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 125,
      "description": "Bare except clause hides unexpected errors and makes debugging difficult",
      "suggested_fix": "Catch specific exceptions:\n```python\nexcept (ET.ParseError, AttributeError, KeyError, ValueError) as e:\n    logger.error(\"evaluation_error\", error_type=type(e).__name__, error=str(e))\n    result = False\n    details = f\"Evaluation failed: {type(e).__name__}\"\n```"
    },
    {
      "severity": "critical",
      "category": "testing",
      "file": "mortgage_underwriting/tests/conftest.py",
      "line": 6,
      "description": "Wrong module and model name in test imports - will cause test failures",
      "suggested_fix": "Correct the imports:\n```python\nfrom mortgage_underwriting.modules.policy.models import LenderPolicy, PolicyEvaluation\n```"
    },
    {
      "severity": "high",
      "category": "security",
      "file": "mortgage_underwriting/modules/policy/routes.py",
      "line": 26,
      "description": "Public endpoints lack rate limiting, vulnerable to DoS attacks",
      "suggested_fix": "Add rate limiting:\n```python\nfrom slowapi import Limiter\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.get(\"/lenders\", response_model=PolicyListResponse)\n@limiter.limit(\"100/minute\")\nasync def list_lender_policies(...):\n```"
    },
    {
      "severity": "high",
      "category": "security",
      "file": "mortgage_underwriting/modules/policy/routes.py",
      "line": 29,
      "description": "Endpoints missing authentication - anyone can create/update policies",
      "suggested_fix": "Add auth dependency:\n```python\nfrom mortgage_underwriting.common.security import verify_token\n\nasync def list_lender_policies(\n    _: str = Depends(verify_token),\n    service: PolicyService = Depends(get_policy_service)\n):\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/routes.py",
      "line": 46,
      "description": "Error response format inconsistent with project convention - uses 'message' instead of 'detail'",
      "suggested_fix": "Change error response format:\n```python\ndetail={\"detail\": \"Failed to fetch policies\", \"error_code\": \"POLICY_FETCH_ERROR\"}\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 132,
      "description": "Application data serialized with str() instead of proper JSON format",
      "suggested_fix": "Use json.dumps:\n```python\nimport json\napplication_data=json.dumps(payload.application_data)\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 60,
      "description": "Duplicate XML validation logic in create_policy and update_policy violates DRY principle",
      "suggested_fix": "Extract to helper method:\n```python\ndef _validate_xml_content(xml_content: str) -> None:\n    try:\n        ET.fromstring(xml_content)\n    except ET.ParseError as e:\n        raise InvalidXMLFormatError(f\"Invalid XML format: {str(e)}\")\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 74,
      "description": "No transaction rollback on failure - database could be left in inconsistent state",
      "suggested_fix": "Use transaction context manager:\n```python\nasync with self.db.begin():\n    self.db.add(policy)\n    await self.db.flush()\n    await self.db.refresh(policy)\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 29,
      "description": "Magic number 100 for max page size should be a constant",
      "suggested_fix": "Define constant:\n```python\nMAX_PAGE_SIZE = 100\nif size > MAX_PAGE_SIZE:\n    size = MAX_PAGE_SIZE\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/policy/schemas.py",
      "line": 12,
      "description": "LenderPolicyUpdate schema only allows xml_content updates, missing name/version/is_active fields",
      "suggested_fix": "Expand update schema:\n```python\nclass LenderPolicyUpdate(BaseModel):\n    name: Optional[str] = Field(None, max_length=255)\n    xml_content: Optional[str] = None\n    version: Optional[str] = Field(None, max_length=20)\n    is_active: Optional[bool] = None\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/policy/models.py",
      "line": 28,
      "description": "Missing composite index on (policy_id, created_at) for common time-range queries",
      "suggested_fix": "Add composite index:\n```python\n__table_args__ = (\n    Index('ix_policy_evaluations_policy_id', 'policy_id'),\n    Index('ix_policy_evaluations_created_at', 'created_at'),\n    Index('ix_policy_evaluations_policy_created', 'policy_id', 'created_at'),\n)\n```"
    },
    {
      "severity": "medium",
      "category": "observability",
      "file": "mortgage_underwriting/modules/policy/services.py",
      "line": 27,
      "description": "structlog calls missing correlation_id for distributed tracing",
      "suggested_fix": "Add correlation_id to log context:\n```python\nlogger.info(\"fetching_all_policies\", page=page, size=size, correlation_id=get_correlation_id())\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/policy/routes.py",
      "line": 27,
      "description": "Excessive blank lines between decorator and function definition",
      "suggested_fix": "Remove extra blank lines to maintain PEP 8 standards"
    }
  ],
  "summary": "Module is BLOCKED due to critical security vulnerabilities (XML bomb, missing auth/rate limiting), regulatory compliance failures (OSFI B-20 stress test not applied), and data integrity issues (missing foreign key). Additionally, code has invalid import syntax, uses float for monetary values, lacks proper error handling, and has no test coverage. All critical issues must be resolved before approval."
}
```