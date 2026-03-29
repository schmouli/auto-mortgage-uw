✅ PASS: Table has id (PK) — models.py — MortgageApplication includes `id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)`  
✅ PASS: Financial column uses Numeric(15, 2) — models.py line 12 — `purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)`  
❌ FAIL: Missing updated_at auto-update — models.py line 16 — add `onupdate=func.now()` to `updated_at` field (present but double-check alignment)  
✅ PASS: Foreign key has index — models.py line 10 — `client_id` is indexed  
❌ FAIL: Foreign key ondelete policy missing — models.py line 10 — add `ondelete="CASCADE"` or appropriate behavior to ForeignKey  
❌ FAIL: Missing created_at and updated_at in Pydantic schema — schemas.py — Add `created_at` and `updated_at` to `ApplicationResponse` for audit traceability  
✅ PASS: Input validation present in service layer — services.py lines 17–25 — validates `purchase_price > 0`  
✅ PASS: Error handling with structured response — routes.py lines 23–25 — raises HTTPException with detail and error_code  

FINAL VERDICT:
BLOCKED

📚 LEARNINGS (compressed):
1. [high] Always specify `ondelete` policy for foreign keys to ensure referential integrity during CASCADE operations
2. [high] Include `created_at`/`updated_at` in response schemas for audit compliance (FINTRAC/OSFI)
3. [med] Ensure `onupdate=func.now()` is applied correctly and consistently across all `updated_at` fields
4. [low] Validate that all Decimal fields use sufficient scale/precision (e.g., Numeric(19,4) for broader currency compatibility)