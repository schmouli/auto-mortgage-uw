✅ PASS: Table has id (PK) — models.py — MortgageApplication includes `id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)`  
✅ PASS: Table has created_at, updated_at audit fields — models.py — Both fields present with `server_default=func.now()` and `onupdate=func.now()`  
✅ PASS: Financial columns use Numeric(15, 2) — models.py line 12 — `purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)`  
❌ FAIL: Foreign Key ondelete behavior — models.py line 13 — Add explicit `ondelete=` clause to ForeignKey definition (e.g., `'CASCADE'`, `'SET NULL'`, or `'RESTRICT'`) based on business logic  
✅ PASS: Indexes on FKs — models.py line 13 — `index=True` specified for `client_id`  
✅ PASS: Type hints in schemas — schemas.py — All fields have proper type annotations including Decimal  
✅ PASS: Input validation for financial values — services.py line 15–17 — Explicit check for `purchase_price > Decimal('100000000')` raises ValueError  
✅ PASS: Structured error responses — routes.py line 32–33 — HTTPException returns dict with `"detail"` and `"error_code"`  
✅ PASS: Return type annotations in route handler — routes.py line 23 — Function annotated with `-> ApplicationResponse`  

FINAL VERDICT:
BLOCKED

📚 LEARNINGS (compressed):
1. [high] Always specify `ondelete` behavior for foreign keys to ensure referential integrity and safe cascading
2. [medium] Validate all user inputs early using Pydantic validators or service-level checks
3. [low] Prefer Decimal over float/int for all monetary values to prevent precision loss
4. [low] Include complete audit fields (`created_at`, `updated_at`) with timezone awareness
5. [info] Ensure structured logging and consistent error handling across layers