⚠️ **BLOCKED**

**CRITICAL ISSUES (Must fix before merge)**

1. **[CRITICAL]** `services.py` ~L115-125: OSFI B-20 regulatory violation — GDS/TDS checks are hardcoded placeholders (`value: 30.0`, `value: 35.0`) without stress test logic. Must implement: `qualifying_rate = max(contract_rate + 2%, 5.25%)`, enforce hard limits (GDS ≤ 39%, TDS ≤ 44%), and log calculation breakdowns for auditability.

2. **[CRITICAL]** `services.py` ~L105-108 & ~L70: Float usage for monetary values violates absolute rule. `float(ltv)`, `float(max_ltv)` in check results and `float(policy.version)` in version bump cause precision loss. **Fix**: Keep all financial values as `Decimal` throughout; use `Decimal` for version arithmetic.

3. **[CRITICAL]** `exceptions.py` vs `services.py` vs `routes.py`: Exception mismatch causes 500 errors. `exceptions.py` defines `PolicyNotFoundError` but `services.py` imports `NotFoundError` from `common.exceptions`, and `routes.py` catches the wrong type. **Fix**: Unify strategy — either use module-specific exceptions everywhere or import from `common.exceptions` consistently.

4. **[CRITICAL]** `models.py` ~L45: ForeignKey missing `ondelete` behavior. `policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("lender_policies.id"), nullable=False)` must specify `ondelete='CASCADE'` (or appropriate action) per database pattern requirements.

5. **[CRITICAL]** `routes.py` ~L78 & ~L92: Bare `except Exception:` violates error handling conventions. Catches all exceptions indiscriminately, masking bugs. **Fix**: Catch specific exceptions (`PolicyParsingError`, `PolicyEvaluationError`) and log appropriately before returning structured errors.

**ADDITIONAL WARNINGS** (address after critical issues):
- `services.py` ~L95: No validation of XML numeric values before `Decimal()` conversion — add try/except with meaningful error
- `services.py`: Magic numbers `0.8` (LTV threshold) and `0.1` (version increment) should be module constants
- `models.py`: `PolicyEvaluation.details` uses `Text` column for JSON — consider `JSONB` for PostgreSQL 15 for queryability
- `tests.py`: References non-existent `xml_policy_service` module — tests must match actual `policy` module structure
- No PIPEDA encryption logic visible for PII fields (SIN/DOB) in `applicant_data`
- No FINTRAC transaction flagging logic for amounts > CAD $10,000
- No CMHC insurance premium tier lookup implementation
- Missing transaction context manager (`async with self.db.begin()`) for atomic operations