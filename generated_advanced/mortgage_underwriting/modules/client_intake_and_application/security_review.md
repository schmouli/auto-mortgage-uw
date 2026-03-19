**AUDIT VERDICT: BLOCKED**  

The Client Intake & Application module contains multiple critical security and compliance violations that must be remediated before deployment.

---

### 🔴 Critical Findings

| # | Severity | Affected File | Vulnerable Code Pattern | Recommended Fix |
|---|----------|---------------|--------------------------|-----------------|
| 1 | **Critical** | `routes.py` (all endpoints) | No authentication or authorization dependencies (e.g., `Depends(get_current_user)`). No ownership checks. | Add JWT/OAuth2 dependency to every endpoint. Enforce role-based access: clients can only view/own data, brokers see their clients, admins see all. Verify `client_id`/`application_id` belongs to the caller. |
| 2 | **Critical** | `models.py` – `Client.date_of_birth` | DOB stored as plain `DateTime`, not encrypted. | Encrypt DOB at rest using `common.security.encrypt_pii()` before persistence; store ciphertext in a `Text` column. |
| 3 | **Critical** | `models.py` – `Client.annual_income`, `Client.other_income`, `CoBorrower.annual_income` | Income stored as plain `Numeric`, not encrypted. | Encrypt all income fields at rest; store ciphertext in `Text` columns. |
| 4 | **High** | `models.py` – all tables | Missing `created_by`/`updated_by` audit fields. FINTRAC/OSFI require immutable audit trail with user identity. | Add `created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))` and `updated_by` to every model. Populate from JWT token. |
| 5 | **High** | `models.py` – `Client`, `Application`, `CoBorrower` | Foreign keys use `ondelete="CASCADE"` → hard deletes. FINTRAC mandates 5-year retention. | Remove `ondelete="CASCADE"`; implement soft-delete (`deleted_at: Mapped[Optional[datetime]]`) and filter queries accordingly. |
| 6 | **Medium** | `routes.py` – blanket `except Exception as e` | Generic exception handlers return `detail=str(e)`, risking internal stack trace leakage if debug is enabled. | Catch specific exceptions (`AppException`, `NotFoundError`) and map to structured error responses; avoid exposing raw exception messages. |
| 7 | **Medium** | `routes.py` – all endpoints | No rate‑limiting middleware; susceptible to brute‑force enumeration of `application_id`. | Apply a FastAPI rate‑limiter (e.g., `slowapi`) to limit requests per IP/JWT. |
| 8 | **Low** | `models.py` – `Application.property_address` (JSONB) | Address stored unencrypted; may contain PII. | Assess risk: if address is PII, encrypt the JSON blob before storage. |

---

### 📚 LEARNINGS (compressed)

1. **[critical]** Add JWT auth and ownership checks to all endpoints to prevent IDOR and broken access control.  
2. **[critical]** Encrypt DOB and income fields at rest for PIPEDA compliance.  
3. **[high]** Add `created_by`/`updated_by` audit fields for FINTRAC/OSFI traceability.  
4. **[high]** Replace hard deletes with soft deletes for 5‑year retention.  
5. **[medium]** Avoid generic exception handlers to prevent information leakage.  
6. **[medium]** Implement rate limiting to mitigate abuse.  

---

### CVE References
**N/A** – No known CVEs affect the libraries or code patterns used in this module. The issues are architectural and compliance‑related rather than known software vulnerabilities.