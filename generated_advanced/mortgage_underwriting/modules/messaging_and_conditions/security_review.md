**AUDIT VERDICT: BLOCKED**

---

### Summary
The **Messaging & Conditions** module contains multiple high‑severity security and compliance violations that expose the system to unauthorized data access and regulatory penalties under **PIPEDA**, **FINTRAC**, and **OSFI B‑20**. The most critical issues are **broken access control (IDOR)** and **lack of encryption for PII‑bearing free‑text fields**. These must be remediated before the code can be approved for production.

---

### 1. Broken Access Control (IDOR) – **HIGH**
**CWE‑284: Improper Access Control**

| File | Vulnerable Code Pattern | Recommended Fix |
|------|------------------------|-----------------|
| `services.py` – `MessagingService.get_message_thread()` | No check that `current_user` is a participant in `application_id`. | Add a policy check: query the `mortgage_applications` participant list and verify `current_user.user_id` is present before fetching messages. |
| `services.py` – `MessagingService.send_message()` | No verification that `sender_id` or `payload.recipient_id` belong to the application. | Validate that both IDs are participants in the application; reject if not. |
| `services.py` – `ConditionService.add_condition()` | No authorization check on `application_id`. | Ensure `current_user` has a role (e.g., underwriter, broker) that allows adding conditions to the specified application. |
| `services.py` – `ConditionService.list_conditions()` / `list_outstanding_conditions()` | No ownership/participation check. | Restrict queries to applications the user is authorized to view. |
| `services.py` – `ConditionService.update_condition_status()` | Only checks `application_id` match; does not verify user role or ownership. | Enforce role‑based permission: only the assignee or an underwriter may update the status; set `satisfied_by` server‑side. |
| `routes.py` – All endpoints | `verify_token` is used, but no further ACL logic. | Add a dependency (`get_current_participant`) that resolves the user’s role and application membership; inject into each endpoint. |

**Impact:** An attacker with a valid JWT can read, write, or modify messages and conditions for **any mortgage application** by guessing or enumerating `application_id`s.

---

### 2. PII Encryption at Rest – **HIGH**
**PIPEDA Requirement: SIN, DOB, and other sensitive personal information must be encrypted (AES‑256) when stored.**

| File | Vulnerable Code Pattern | Recommended Fix |
|------|------------------------|-----------------|
| `models.py` – `Message.body` | Stored as plain `Text`. | Use `common/security.encrypt_pii()` before persisting; store ciphertext in a `LargeBinary` column. |
| `models.py` – `Condition.description` | Stored as plain `Text`. | Apply the same encryption transformation. |
| `schemas.py` – `MessageCreateRequest.body` / `ConditionCreateRequest.description` | No sanitization or encryption logic. | Introduce a pre‑save hook in the service layer that encrypts these fields. |
| `services.py` – `send_message()`, `add_condition()` | Directly pass raw text into the DB. | Encrypt `body`/`description` before instantiation of the ORM object. |
| `services.py` – `get_message_thread()`, `list_conditions()` | Return decrypted text to the client. | Decrypt on read within the service layer; ensure the response model masks any residual PII (e.g., show only last 4 digits of SIN). |

**Impact:** Non‑compliance with PIPEDA; a database breach exposes plaintext PII, leading to regulatory fines and reputational damage.

---

### 3. Inadequate Audit Trail (Immutability & `created_by`) – **MEDIUM**
**FINTRAC & OSFI B‑20: All financial‑related records must be immutable and include `created_by`.**

| File | Vulnerable Code Pattern | Recommended Fix |
|------|------------------------|-----------------|
| `models.py` – `Message` | No `created_by` column; relies on implicit `sender_id`. | Add `created_by: Mapped[int]` and populate with `current_user.user_id`. |
| `models.py` – `Condition` | `updated_at` is mutable; no `created_by`. | Add `created_by` and treat `updated_at` as a read‑only audit field; log all status changes in a separate immutable audit table. |
| `models.py` – ForeignKey `ondelete="CASCADE"` | Deleting an application erases all messages/conditions. | Replace with soft‑delete (`is_deleted` flag) and a retention job that archives after 5 years. |

**Impact:** Loss of forensic evidence; inability to prove compliance during an audit.

---

### 4. Client‑Controlled System Fields – **MEDIUM**
**CWE‑20: Improper Input Validation**

| File | Vulnerable Code Pattern | Recommended Fix |
|------|------------------------|-----------------|
| `schemas.py` – `ConditionUpdateRequest.satisfied_at`, `satisfied_by` | Accepts arbitrary datetime/user ID. | Remove these fields from the request schema; set `satisfied_at=func.now()` and `satisfied_by=current_user.user_id` in the service layer. |

**Impact:** A malicious client can falsify audit timestamps and impersonate other users.

---

### 5. Information Disclosure via Error Messages – **LOW**
**CWE‑209: Generation of Error Message Containing Sensitive Information**

| File | Vulnerable Code Pattern | Recommended Fix |
|------|------------------------|-----------------|
| `services.py` – `NotFoundError` details | `"Message not found or unauthorized access"` reveals existence. | Use a generic message: `"Resource not found"` to prevent user enumeration. |

---

### 6. Timezone‑Naive Timestamp – **LOW**
**CWE‑237: Improper Handling of Date/Time**

| File | Vulnerable Code Pattern | Recommended Fix |
|------|------------------------|-----------------|
| `services.py` – `mark_as_read()` uses `datetime.now()`. | Naive datetime stored in `read_at`. | Replace with `func.now()` or `datetime.now(timezone.utc)`. |

---

### 7. Missing Rate Limiting & Response Headers – **LOW (out‑of‑scope)**
- Rate limiting and security headers (CSP, HSTS, X‑Frame‑Options) should be configured at the **FastAPI app level**, not per module. Ensure they are present before deployment.

---

### CVE / CWE References
- **IDOR**: CWE‑284 (Improper Access Control) – *No specific CVE; exploitability depends on business context.*
- **PII Encryption**: PIPEDA non‑compliance; analogous to **CVE‑2020‑15598** (unencrypted sensitive data at rest).
- **Client‑Controlled Fields**: CWE‑20 (Improper Input Validation).
- **Information Disclosure**: CWE‑209.

---

### Remediation Checklist
1. **Authorization Layer** – Introduce `get_current_participant()` dependency; enforce membership checks on all endpoints.  
2. **Encryption** – Apply `encrypt_pii()` to `Message.body` and `Condition.description`; store ciphertext.  
3. **Audit Columns** – Add `created_by` to both models; implement soft‑delete instead of `CASCADE`.  
4. **Server‑Side Timestamps** – Remove `satisfied_at`/`satisfied_by` from client payload; set automatically.  
5. **Error Message Hardening** – Use generic “not found” messages.  
6. **Timezone Awareness** – Use `func.now()` or UTC‑aware datetimes.  
7. **Rate Limiting & Headers** – Verify app‑level middleware is configured.  

After addressing the **HIGH** severity items (IDOR & PII encryption), re‑audit the module to ensure compliance before merging.