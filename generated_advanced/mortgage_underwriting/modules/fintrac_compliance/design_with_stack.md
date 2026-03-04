# Design: FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: OnLendHub - Canadian Mortgage Underwriting

# FINTRAC Compliance Module Architecture - OnLendHub

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Gateway (Kong)                            │
│                    (Rate Limiting, mTLS Termination)                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐    ┌──────▼────────┐    ┌───────▼────────┐
│  Verification  │    │  Transaction  │    │   Reporting    │
│    Service     │    │   Monitor     │    │    Service     │
│  (FastAPI)     │    │  (FastAPI)    │    │   (FastAPI)    │
└───────┬────────┘    └──────┬────────┘    └───────┬────────┘
        │                    │                      │
        │  ┌─────────────────┼─────────────────┐    │
        │  │                 │                 │    │
┌───────▼──▼────────┐  ┌────▼──────┐    ┌──────▼────────┐
│  Risk Engine      │  │  Workflow │    │  PEP/HIO Sync │
│  (Python/ML)      │  │ (Temporal)│    │  (TypeScript) │
└─────────┬─────────┘  └────┬──────┘    └──────┬────────┘
          │                 │                  │
          │  ┌──────────────┼──────────────────┼──────────────┐
          │  │              │                  │              │
┌─────────▼──▼────────┐ ┌──▼────────┐   ┌────▼──────┐   ┌────▼──────┐
│   PostgreSQL        │ │  Redis    │   │  Kafka    │   │  Vault    │
│  (Encrypted)        │ │  (Cache)  │   │ (Events)  │   │  (KMS)    │
│                     │ │           │   │           │   │           │
│ ┌─────────────────┐ │ │           │   │           │   │           │
│ │fintrac_verifs   │ │ │           │   │           │   │           │
│ │fintrac_reports  │ │ │           │   │           │   │           │
│ │audit_log        │ │ │           │   │           │   │           │
│ │soft_deletes     │ │ │           │   │           │   │           │
│ └─────────────────┘ │ │           │   │           │   │           │
└─────────────────────┘ └───────────┘   └───────────┘   └───────────┘
```

---

## 2. Service Layer Design

### 2.1 Verification Service (FastAPI)
**Responsibilities**: Identity verification, risk level calculation, PEP/HIO screening

```python
# Core endpoints implementation
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from pydantic import BaseModel, Field
from enum import Enum

router = APIRouter(prefix="/fintrac/applications")

class VerificationMethod(str, Enum):
    IN_PERSON = "in_person"
    CREDIT_FILE = "credit_file"
    DUAL_PROCESS = "dual_process"

class IdentityVerificationRequest(BaseModel):
    verification_method: VerificationMethod
    id_type: str
    id_number: str  # Plaintext - encrypted at rest
    id_expiry_date: date
    id_issuing_province: str
    amount: Decimal = Field(..., description="Mortgage amount for threshold check")

class RiskAssessmentResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    is_pep: bool
    is_hio: bool
    requires_edd: bool
    factors: List[str]

@router.post("/{application_id}/verify-identity", status_code=201)
async def verify_identity(
    application_id: UUID,
    request: IdentityVerificationRequest,
    db: AsyncSession = Depends(get_db),
    vault: VaultClient = Depends(get_vault),
    pep_service: PEPService = Depends()
):
    """
    Multi-step verification process:
    1. Validate ID document format and expiry
    2. Check against PEP/HIO databases (real-time)
    3. Calculate risk score based on 15+ factors
    4. Encrypt PII using envelope encryption
    5. Store with immutable audit trail
    """
    
    # Step 1: Validate ID document
    if request.id_expiry_date < date.today():
        raise HTTPException(400, "ID document expired")
    
    # Step 2: Real-time PEP/HIO screening
    screening_result = await pep_service.screen_individual(
        name=applicant_name,
        dob=applicant_dob,
        id_number=request.id_number
    )
    
    # Step 3: Risk scoring engine
    risk_score = await calculate_risk_score(
        application_id,
        request,
        screening_result,
        db
    )
    
    # Step 4: Encrypt ID number using envelope encryption
    encryption_key = await vault.generate_data_key("fintrac-transit")
    encrypted_id = await vault.encrypt(
        plaintext=request.id_number,
        key_id=encryption_key
    )
    
    # Step 5: Store with versioning
    verification_record = FintracVerification(
        application_id=application_id,
        client_id=client_id,
        verification_method=request.verification_method,
        id_type=request.id_type,
        id_number_encrypted=encrypted_id,
        id_expiry_date=request.id_expiry_date,
        id_issuing_province=request.id_issuing_province,
        verified_by=current_user.id,
        is_pep=screening_result.is_match,
        is_hio=screening_result.is_hio,
        risk_level=risk_score.level,
        risk_score=risk_score.value,
        encryption_key_id=encryption_key.id
    )
    
    db.add(verification_record)
    await db.commit()
    
    # Step 6: Emit event for audit
    await kafka_producer.send(
        topic="fintrac.verification.created",
        value={
            "verification_id": str(verification_record.id),
            "application_id": str(application_id),
            "risk_level": risk_score.level,
            "requires_edd": risk_score.requires_edd
        }
    )
    
    return {
        "verification_id": verification_record.id,
        "risk_level": risk_score.level,
        "requires_edd": risk_score.requires_edd,
        "next_steps": await generate_compliance_checklist(risk_score)
    }
```

### 2.2 Transaction Monitoring Service
**Responsibilities**: Real-time transaction analysis, structuring detection, threshold monitoring

```python
class TransactionMonitor:
    """
    Implements FINTRAC LCTR (Large Cash Transaction Report) rules
    and structuring detection using sliding window algorithm
    """
    
    def __init__(self, redis: Redis, db: AsyncSession):
        self.redis = redis
        self.db = db
        self.LCTR_THRESHOLD = Decimal("10000.00")
        self.STRUCTURING_WINDOW = timedelta(hours=24)
        self.STRUCTURING_COUNT_THRESHOLD = 3
    
    async def process_cash_transaction(
        self,
        application_id: UUID,
        amount: Decimal,
        currency: str
    ) -> Optional[FintracReport]:
        """
        Real-time transaction monitoring with event sourcing
        """
        
        # Convert to CAD if needed
        cad_amount = await self.convert_to_cad(amount, currency)
        
        # Check LCTR threshold
        if cad_amount > self.LCTR_THRESHOLD:
            return await self.create_lctr_report(
                application_id,
                cad_amount,
                "large_cash_transaction"
            )
        
        # Check for structuring patterns
        if await self.detect_structuring(application_id, cad_amount):
            return await self.create_lctr_report(
                application_id,
                cad_amount,
                "suspicious_transaction",
                reason="potential_structuring"
            )
        
        # Log for audit trail
        await self.log_transaction_event(application_id, cad_amount)
        return None
    
    async def detect_structuring(
        self,
        application_id: UUID,
        amount: Decimal
    ) -> bool:
        """
        Sliding window detection of structuring (smurfing)
        Stores transaction metadata in Redis with TTL
        """
        
        window_key = f"txn_window:{application_id}"
        current_time = datetime.utcnow()
        
        # Get transactions in last 24h
        recent_txns = await self.redis.zrangebyscore(
            window_key,
            min=current_time - self.STRUCTURING_WINDOW,
            max=current_time
        )
        
        # Count transactions below threshold
        structuring_count = sum(
            1 for txn in recent_txns
            if Decimal(txn.decode()) < self.LCTR_THRESHOLD
        )
        
        # Add current transaction to window
        await self.redis.zadd(window_key, {str(amount): current_time.timestamp()})
        await self.redis.expire(window_key, self.STRUCTURING_WINDOW)
        
        return structuring_count >= self.STRUCTURING_COUNT_THRESHOLD
```

---

## 3. Enhanced Database Schema

```sql
-- Main verification table with row-level security
CREATE TABLE fintrac_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id),
    client_id UUID NOT NULL REFERENCES clients(id),
    verification_method VARCHAR(20) CHECK (verification_method IN ('in_person', 'credit_file', 'dual_process')),
    id_type VARCHAR(50) NOT NULL,
    id_number_encrypted BYTEA NOT NULL, -- Encrypted with AES-256-GCM
    id_expiry_date DATE NOT NULL,
    id_issuing_province VARCHAR(2) CHECK (id_issuing_province ~ '^[A-Z]{2}$'),
    verified_by UUID NOT NULL REFERENCES users(id),
    verified_at TIMESTAMPTZ DEFAULT NOW(),
    is_pep BOOLEAN NOT NULL DEFAULT FALSE,
    is_hio BOOLEAN NOT NULL DEFAULT FALSE,
    risk_level VARCHAR(10) CHECK (risk_level IN ('low', 'medium', 'high')),
    risk_score NUMERIC(5,2), -- 0.00 to 100.00
    
    -- Encryption metadata
    encryption_key_id UUID NOT NULL,
    encryption_version INTEGER DEFAULT 1,
    
    -- Soft delete compliance
    deleted_at TIMESTAMPTZ,
    deleted_by UUID REFERENCES users(id),
    delete_reason TEXT,
    
    -- Row-level security
    tenant_id UUID NOT NULL,
    
    -- Performance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT no_hard_delete CHECK (deleted_at IS NOT NULL OR TRUE) -- Prevent hard deletes
);

-- Enable row-level security
ALTER TABLE fintrac_verifications ENABLE ROW LEVEL SECURITY;

-- Index for compliance queries
CREATE INDEX idx_verifications_application ON fintrac_verifications(application_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_client ON fintrac_verifications(client_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_risk ON fintrac_verifications(risk_level, verified_at);
CREATE INDEX idx_verifications_pep_hio ON fintrac_verifications(is_pep, is_hio) WHERE is_pep = TRUE OR is_hio = TRUE;

-- Immutable audit log table
CREATE TABLE fintrac_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(10) CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    changed_by UUID NOT NULL REFERENCES users(id),
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    
    -- Tamper detection
    previous_hash VARCHAR(64),
    current_hash VARCHAR(64) NOT NULL,
    
    -- Compliance metadata
    compliance_rule_triggered VARCHAR(100),
    
    -- Partition by month for performance
) PARTITION BY RANGE (changed_at);

-- Create monthly partitions
CREATE TABLE fintrac_audit_log_2024_01 PARTITION OF fintrac_audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Reports table with status tracking
CREATE TABLE fintrac_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id),
    report_type VARCHAR(30) CHECK (report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')),
    amount NUMERIC(15,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CAD',
    report_date DATE NOT NULL,
    submitted_to_fintrac_at TIMESTAMPTZ,
    fintrac_reference_number VARCHAR(50),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'acknowledged', 'rejected')),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Retry logic
    submission_attempts INTEGER DEFAULT 0,
    last_error TEXT,
    
    -- XML payload storage (encrypted)
    fintrac_payload_encrypted BYTEA,
    
    -- Soft delete
    deleted_at TIMESTAMPTZ,
    
    CONSTRAINT unique_fintrac_ref UNIQUE (fintrac_reference_number)
);

-- Soft delete tracking table (5-year retention)
CREATE TABLE fintrac_soft_deletes (
    id UUID PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    deleted_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_by UUID NOT NULL REFERENCES users(id),
    delete_reason TEXT NOT NULL,
    retention_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '5 years',
    data_snapshot JSONB NOT NULL -- Full record snapshot for audit
);

CREATE INDEX idx_soft_deletes_retention ON fintrac_soft_deletes(retention_until) WHERE retention_until > NOW();
```

---

## 4. Risk Scoring Engine Implementation

```python
class RiskScoringEngine:
    """
    Multi-factor risk scoring algorithm based on FINTRAC guidance
    Weights are configurable and versioned
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.weights = {
            "pep_status": 30.0,
            "hio_status": 25.0,
            "geographic_risk": 15.0,
            "transaction_amount": 10.0,
            "id_verification_method": 10.0,
            "client_age": 5.0,
            "historical_activity": 5.0
        }
    
    async def calculate_score(
        self,
        application_id: UUID,
        verification_request: IdentityVerificationRequest,
        pep_result: ScreeningResult
    ) -> RiskScore:
        
        score_components = {}
        total_score = 0.0
        
        # Factor 1: PEP/HIO status (highest weight)
        if pep_result.is_pep:
            score_components["pep_status"] = self.weights["pep_status"]
            total_score += self.weights["pep_status"]
        
        if pep_result.is_hio:
            score_components["hio_status"] = self.weights["hio_status"]
            total_score += self.weights["hio_status"]
        
        # Factor 2: Geographic risk (province-based)
        geo_risk = await self.get_geographic_risk(
            verification_request.id_issuing_province
        )
        score_components["geographic_risk"] = geo_risk * self.weights["geographic_risk"]
        total_score += score_components["geographic_risk"]
        
        # Factor 3: Transaction amount risk
        if verification_request.amount > Decimal("500000"):
            amount_risk = 1.0
        elif verification_request.amount > Decimal("250000"):
            amount_risk = 0.7
        else:
            amount_risk = 0.3
        
        score_components["transaction_amount"] = amount_risk * self.weights["transaction_amount"]
        total_score += score_components["transaction_amount"]
        
        # Factor 4: ID verification method
        method_risk = {
            VerificationMethod.IN_PERSON: 0.1,
            VerificationMethod.CREDIT_FILE: 0.5,
            VerificationMethod.DUAL_PROCESS: 0.3
        }[verification_request.verification_method]
        
        score_components["id_verification_method"] = method_risk * self.weights["id_verification_method"]
        total_score += score_components["id_verification_method"]
        
        # Determine risk level
        if total_score >= 60:
            risk_level = "high"
        elif total_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Check if Enhanced Due Diligence required
        requires_edd = (
            risk_level == "high" or 
            pep_result.is_pep or 
            pep_result.is_hio
        )
        
        return RiskScore(
            value=round(total_score, 2),
            level=risk_level,
            requires_edd=requires_edd,
            components=score_components,
            version="2.1"
        )
```

---

## 5. PEP/HIO Automated Integration Service

```typescript
// TypeScript service for watchlist management
import { Injectable, OnModuleInit } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { Redis } from 'ioredis';
import { WorldCheckAPI } from './providers/worldcheck.api';
import { LexisNexisAPI } from './providers/lexisnexis.api';

interface WatchlistEntry {
  id: string;
  name: string;
  dateOfBirth?: string;
  type: 'pep' | 'hio' | 'sanction';
  source: string;
  lastUpdated: Date;
  metadata: Record<string, any>;
}

@Injectable()
export class WatchlistSyncService implements OnModuleInit {
  private readonly WATCHLIST_VERSION_KEY = 'pep_hio:version';
  private readonly WATCHLIST_INDEX_KEY = 'pep_hio:index';
  
  constructor(
    private readonly redis: Redis,
    private readonly worldCheck: WorldCheckAPI,
    private readonly lexisNexis: LexisNexisAPI
  ) {}

  async onModuleInit() {
    // Load watchlist into Redis on startup
    await this.loadWatchlistIntoMemory();
  }

  @Cron(CronExpression.EVERY_DAY_AT_2AM)
  async syncWatchlists(): Promise<void> {
    /**
     * Automated daily sync from multiple providers
     * Uses incremental updates where possible
     */
    
    const currentVersion = await this.redis.get(this.WATCHLIST_VERSION_KEY);
    const newVersion = Date.now().toString();
    
    try {
      // Fetch delta updates from providers
      const [wcUpdates, lnUpdates] = await Promise.all([
        this.worldCheck.getUpdatesSince(currentVersion),
        this.lexisNexis.getUpdatesSince(currentVersion)
      ]);

      // Merge and deduplicate
      const mergedUpdates = this.mergeWatchlistUpdates([
        ...wcUpdates,
        ...lnUpdates
      ]);

      // Update Redis in transaction
      const pipeline = this.redis.pipeline();
      
      // Build search index (name -> entry)
      for (const entry of mergedUpdates) {
        const key = `pep_hio:entry:${entry.id}`;
        pipeline.hset(key, this.serializeEntry(entry));
        pipeline.expire(key, 86400 * 7); // 7 day TTL
        
        // Add to search index
        pipeline.zadd(
          this.WATCHLIST_INDEX_KEY,
          entry.name.toLowerCase(),
          key
        );
      }

      // Update version
      pipeline.set(this.WATCHLIST_VERSION_KEY, newVersion);
      
      await pipeline.exec();
      
      // Emit metrics
      this.emitWatchlistMetrics(mergedUpdates.length);
      
    } catch (error) {
      // Fail-safe: keep old version if sync fails
      console.error('Watchlist sync failed, keeping previous version', error);
      throw error;
    }
  }

  async screenIndividual(
    name: string,
    dob?: string,
    idNumber?: string
  ): Promise<ScreeningResult> {
    /**
     * Real-time screening using Redis Bloom filter for performance
     * Falls back to API call on potential match
     */
    
    // Check Bloom filter first (fast path)
    const isPotentialMatch = await this.redis.bf.exists(
      'pep_hio:bloom',
      name.toLowerCase()
    );

    if (!isPotentialMatch) {
      return { isMatch: false, isHio: false };
    }

    // Detailed search on potential match
    const matches = await this.redis.call(
      'FT.SEARCH',
      'pep_hio:index',
      `@name:${this.escapeQuery(name)}`,
      'LIMIT', '0', '10'
    );

    // Fuzzy match and DOB verification
    const verifiedMatches = matches.filter(match => 
      this.verifyMatch(match, name, dob, idNumber)
    );

    return {
      isMatch: verifiedMatches.length > 0,
      isHio: verifiedMatches.some(m => m.type === 'hio'),
      matches: verifiedMatches
    };
  }
}
```

---

## 6. FINTRAC ESTR API Integration

```python
class FINTRACSubmissionClient:
    """
    FINTRAC Electronic Submission (ESTR) API client
    Handles XML generation, signing, and idempotent submission
    """
    
    def __init__(self, vault: VaultClient):
        self.api_base = config.FINTRAC_ESTR_URL
        self.client_cert = vault.get_secret("fintrac/client_cert")
        self.client_key = vault.get_secret("fintrac/client_key")
        self.submitter_id = config.FINTRAC_SUBMITTER_ID
    
    async def submit_report(
        self,
        report: FintracReport,
        verification: FintracVerification
    ) -> SubmissionResult:
        """
        Submit report to FINTRAC with retry logic and idempotency
        """
        
        # Generate FINTRAC-compliant XML payload
        xml_payload = await self.generate_estr_xml(report, verification)
        
        # Sign XML with X.509 certificate
        signed_xml = await self.sign_xml(xml_payload)
        
        # Idempotency key based on report content
        idempotency_key = hashlib.sha256(
            f"{report.id}{report.amount}{report.report_date}".encode()
        ).hexdigest()
        
        # Submit with circuit breaker
        async with self.circuit_breaker:
            try:
                response = await self.http_client.post(
                    f"{self.api_base}/submit",
                    content=signed_xml,
                    headers={
                        "Content-Type": "application/xml",
                        "X-Submitter-ID": self.submitter_id,
                        "X-Idempotency-Key": idempotency_key,
                        "X-Message-Format": "CANADA-FINTRAC-2.0"
                    },
                    cert=(self.client_cert, self.client_key),
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                # Parse FINTRAC response
                result = await self.parse_estr_response(response)
                
                # Update report status
                report.submitted_to_fintrac_at = datetime.utcnow()
                report.fintrac_reference_number = result.reference_number
                report.status = "submitted"
                
                return SubmissionResult(
                    success=True,
                    reference_number=result.reference_number,
                    fintrac_timestamp=result.timestamp
                )
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 409:
                    # Idempotency conflict - report already submitted
                    return await self.handle_duplicate_submission(report, idempotency_key)
                else:
                    await self.log_submission_error(report, e)
                    raise
    
    async def generate_estr_xml(
        self,
        report: FintracReport,
        verification: FintracVerification
    ) -> str:
        """
        Generate FINTRAC ESTR XML v2.0 format
        Includes all required fields: 24-hour rule, indicators, etc.
        """
        
        # Use Jinja2 template with strict validation
        template = self.xml_templates.get_template("fintrac_report.xml")
        
        return template.render({
            "submitter_id": self.submitter_id,
            "report_id": report.id,
            "report_type": report.report_type,
            "transaction_date": report.report_date.isoformat(),
            "amount": format_currency(report.amount),
            "currency": report.currency,
            "client_info": {
                "id_number": await self.get_decrypted_id(verification),
                "id_type": verification.id_type,
                "pep_status": verification.is_pep,
                "hio_status": verification.is_hio
            },
            "indicators": await self.generate_indicators(report),
            "24_hour_rule": await self.check_24_hour_rule(report.application_id)
        })
```

---

## 7. Audit Trail & Immutable Logging

```python
class ImmutableAuditLogger:
    """
    Blockchain-inspired audit logging with hash chaining
    Prevents tampering and provides full lineage
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
    
    async def log_action(
        self,
        table_name: str,
        record_id: UUID,
        action: str,
        old_values: Optional[dict],
        new_values: dict,
        user_id: UUID,
        compliance_rule: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuditLogEntry:
        
        # Get previous hash for chaining
        previous_hash = await self.get_last_hash(table_name, record_id)
        
        # Create hash of current record
        current_hash = self.compute_hash(
            table_name=table_name,
            record_id=record_id,
            action=action,
            new_values=new_values,
            previous_hash=previous_hash
        )
        
        # Insert into audit log
        audit_entry = FintracAuditLog(
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            changed_by=user_id,
            ip_address=ip_address,
            compliance_rule_triggered=compliance_rule,
            previous_hash=previous_hash,
            current_hash=current_hash
        )
        
        self.db.add(audit_entry)
        await self.db.commit()
        
        # Cache latest hash in Redis for performance
        await self.redis.setex(
            f"audit_hash:{table_name}:{record_id}",
            3600,
            current_hash
        )
        
        # Emit to immutable storage (S3 Glacier)
        await self.archive_to_worm_storage(audit_entry)
        
        return audit_entry
    
    def compute_hash(self, **data) -> str:
        """
        Compute SHA-256 hash for tamper detection
        Includes previous hash for chaining
        """
        
        hash_input = json.dumps(data, sort_keys=True)
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    async def verify_chain_integrity(
        self,
        table_name: str,
        record_id: UUID
    ) -> bool:
        """
        Verify hash chain integrity for a record
        Returns True if chain is intact
        """
        
        audit_entries = await self.db.execute(
            select(FintracAuditLog)
            .where(
                FintracAuditLog.table_name == table_name,
                FintracAuditLog.record_id == record_id
            )
            .order_by(FintracAuditLog.changed_at)
        )
        
        previous_hash = None
        for entry in audit_entries.scalars():
            # Recompute hash
            expected_hash = self.compute_hash(
                table_name=entry.table_name,
                record_id=entry.record_id,
                action=entry.action,
                new_values=entry.new_values,
                previous_hash=entry.previous_hash
            )
            
            if expected_hash != entry.current_hash:
                return False
            
            if previous_hash and entry.previous_hash != previous_hash:
                return False
            
            previous_hash = entry.current_hash
        
        return True
```

---

## 8. Record Retention & Soft Delete Implementation

```python
class RetentionManager:
    """
    Manages 5-year retention policy with automated purging
    Tracks soft deletes and ensures immutability
    """
    
    RETENTION_PERIOD = timedelta(days=365 * 5)
    
    async def soft_delete_verification(
        self,
        verification_id: UUID,
        deleted_by: UUID,
        reason: str
    ):
        """
        Soft delete with full audit trail and data snapshot
        """
        
        # Get verification record
        verification = await self.db.get(FintracVerification, verification_id)
        if not verification:
            raise HTTPException(404, "Verification not found")
        
        # Create snapshot for retention
        snapshot = {
            "verification_data": await self.serialize_verification(verification),
            "related_reports": await self.get_related_reports(verification_id),
            "audit_trail": await self.get_audit_history(verification_id)
        }
        
        # Insert into soft deletes table
        soft_delete_record = FintracSoftDelete(
            table_name="fintrac_verifications",
            record_id=verification_id,
            deleted_by=deleted_by,
            delete_reason=reason,
            retention_until=datetime.utcnow() + self.RETENTION_PERIOD,
            data_snapshot=snapshot
        )
        
        self.db.add(soft_delete_record)
        
        # Mark as deleted in main table
        verification.deleted_at = datetime.utcnow()
        verification.deleted_by = deleted_by
        
        # Log the deletion action
        await self.audit_logger.log_action(
            table_name="fintrac_verifications",
            record_id=verification_id,
            action="DELETE",
            old_values=await self.serialize_verification(verification),
            new_values={"deleted_at": verification.deleted_at},
            user_id=deleted_by,
            compliance_rule="RECORD_RETENTION_POLICY"
        )
        
        await self.db.commit()
    
    @cron("0 2 * * *")  # Daily at 2 AM
    async def purge_expired_records(self):
        """
        Automated purging of records past retention period
        Only hard-deletes from soft_deletes table, main table records remain
        """
        
        expired = await self.db.execute(
            select(FintracSoftDelete)
            .where(FintracSoftDelete.retention_until < datetime.utcnow())
        )
        
        for record in expired.scalars():
            # Archive to WORM storage before final purge
            await self.archive_to_worm_storage(record.data_snapshot)
            
            # Hard delete only from soft_deletes table
            await self.db.delete(record)
        
        await self.db.commit()
```

---

## 9. Security & Encryption Architecture

```python
class EncryptionService:
    """
    Envelope encryption using HashiCorp Vault Transit engine
    Supports key rotation and versioning
    """
    
    def __init__(self, vault: VaultClient):
        self.vault = vault
        self.key_name = "fintrac-transit"
    
    async def encrypt_id_number(self, plaintext: str) -> EncryptedData:
        """
        Encrypt ID number with metadata for decryption
        """
        
        # Generate data key from Vault
        data_key = await self.vault.transit.generate_data_key(
            name=self.key_name,
            key_type="plaintext"
        )
        
        # Encrypt locally with data key
        f = Fernet(data_key.plaintext)
        ciphertext = f.encrypt(plaintext.encode())
        
        return EncryptedData(
            ciphertext=ciphertext,
            key_id=data_key.ciphertext,
            key_version=data_key.version,
            algorithm="AES-256-GCM"
        )
    
    async def decrypt_id_number(self, encrypted: EncryptedData) -> str:
        """
        Decrypt using envelope pattern
        """
        
        # Decrypt data key from Vault
        data_key_plaintext = await self.vault.transit.decrypt(
            name=self.key_name,
            ciphertext=encrypted.key_id
        )
        
        # Decrypt data locally
        f = Fernet(data_key_plaintext)
        plaintext = f.decrypt(encrypted.ciphertext)
        
        return plaintext.decode()
    
    async def rotate_encryption_keys(self):
        """
        Annual key rotation for compliance
        Re-encrypts all sensitive data with new key version
        """
        
        # Get all active verifications
        verifications = await self.db.execute(
            select(FintracVerification)
            .where(FintracVerification.deleted_at.is_(None))
        )
        
        new_key_version = await self.vault.transit.rotate_key(self.key_name)
        
        for verification in verifications.scalars():
            # Decrypt with old key
            plaintext = await self.decrypt_id_number(
                EncryptedData(
                    ciphertext=verification.id_number_encrypted,
                    key_id=verification.encryption_key_id,
                    key_version=verification.encryption_version
                )
            )
            
            # Re-encrypt with new key
            new_encrypted = await self.encrypt_id_number(plaintext)
            
            # Update record
            verification.id_number_encrypted = new_encrypted.ciphertext
            verification.encryption_key_id = new_encrypted.key_id
            verification.encryption_version = new_key_version
            
            # Log rotation event
            await self.audit_logger.log_action(
                table_name="fintrac_verifications",
                record_id=verification.id,
                action="UPDATE",
                old_values={"encryption_version": verification.encryption_version},
                new_values={"encryption_version": new_key_version},
                user_id=SYSTEM_USER,
                compliance_rule="ENCRYPTION_KEY_ROTATION"
            )
        
        await self.db.commit()
```

---

## 10. API Specification (OpenAPI 3.1)

```yaml
openapi: 3.1.0
info:
  title: FINTRAC Compliance API
  version: 2.0.0
  description: |
    Canadian mortgage underwriting FINTRAC compliance module
    Implements PCMLTFA requirements for identity verification
    and transaction reporting

paths:
  /fintrac/applications/{id}/verify-identity:
    post:
      summary: Submit identity verification
      parameters:
        - name: id
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [verification_method, id_type, id_number, id_expiry_date, id_issuing_province]
              properties:
                verification_method:
                  type: string
                  enum: [in_person, credit_file, dual_process]
                id_type:
                  type: string
                  enum: [passport, drivers_license, provincial_id, pr_card]
                id_number:
                  type: string
                  pattern: '^[A-Z0-9]{5,20}$'
                id_expiry_date:
                  type: string
                  format: date
                id_issuing_province:
                  type: string
                  pattern: '^[A-Z]{2}$'
                  example: ON
                amount:
                  type: number
                  format: decimal
                  description: Mortgage amount for risk calculation
      responses:
        '201':
          description: Verification created
          content:
            application/json:
              schema:
                type: object
                properties:
                  verification_id: { type: string, format: uuid }
                  risk_level: { type: string, enum: [low, medium, high] }
                  requires_edd: { type: boolean }
                  next_steps:
                    type: array
                    items:
                      type: object
                      properties:
                        action: { type: string }
                        priority: { type: string, enum: [low, medium, high] }
        '422':
          description: Validation error
          content:
            application/problem+json:
              schema:
                type: object
                properties:
                  type: { type: string }
                  title: { type: string }
                  validation_errors:
                    type: array
                    items:
                      type: object
                      properties:
                        field: { type: string }
                        message: { type: string }

  /fintrac/applications/{id}/verification:
    get:
      summary: Get verification status with audit trail
      parameters:
        - name: id
          in: path
          required: true
          schema: { type: string, format: uuid }
        - name: include_audit
          in: query
          schema: { type: boolean, default: false }
      responses:
        '200':
          description: Verification details
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: { type: string, enum: [pending, verified, failed, expired] }
                  risk_assessment:
                    $ref: '#/components/schemas/RiskAssessment'
                  audit_trail:
                    type: array
                    items:
                      $ref: '#/components/schemas/AuditEntry'

components:
  schemas:
    RiskAssessment:
      type: object
      properties:
        risk_level: { type: string, enum: [low, medium, high] }
        risk_score: { type: number, format: float }
        is_pep: { type: boolean }
        is_hio: { type: boolean }
        requires_edd: { type: boolean }
        factors:
          type: array
          items:
            type: object
            properties:
              name: { type: string }
              weight: { type: number }
              value: { type: number }
        calculated_at: { type: string, format: date-time }
    
    AuditEntry:
      type: object
      properties:
        action: { type: string }
        changed_by: { type: string, format: uuid }
        changed_at: { type: string, format: date-time }
        compliance_rule: { type: string }
        hash: { type: string }
        previous_hash: { type: string }
```

---

## 11. Deployment & Observability

```yaml
# docker-compose.yml for local development
version: '3.8'
services:
  fintrac-verification:
    build: 
      context: ./services/verification
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql://fintrac:${DB_PASSWORD}@postgres:5432/onlendhub
      - VAULT_ADDR=http://vault:8200
      - REDIS_URL=redis://redis:6379/0
      - KAFKA_BROKERS=kafka:9092
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    
  postgres:
    image: postgres:15.2
    environment:
      - POSTGRES_DB=onlendhub
      - POSTGRES_USER=fintrac
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - ./init-scripts:/docker-entrypoint-initdb.d
      - postgres_data:/var/lib/postgresql/data
    configs:
      - source: postgres_conf
        target: /etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    
  vault:
    image: hashicorp/vault:1.15
    environment:
      - VAULT_DEV_ROOT_TOKEN_ID=${VAULT_TOKEN}
    cap_add:
      - IPC_LOCK
    configs:
      - source: vault_policy
        target: /vault/config/policy.hcl

# prometheus.yml
scrape_configs:
  - job_name: 'fintrac-services'
    static_configs:
      - targets: 
        - 'fintrac-verification:8000'
        - 'fintrac-transaction:8001'
        - 'fintrac-reporting:8002'
    metrics_path: '/metrics'
    scrape_interval: 15s
    tls_config:
      insecure_skip_verify: false
      cert_file: /etc/prometheus/certs/client.crt
      key_file: /etc/prometheus/certs/client.key

# grafana-dashboard.json (excerpt)
{
  "dashboard": {
    "title": "FINTRAC Compliance Monitoring",
    "panels": [
      {
        "title": "Risk Score Distribution",
        "type": "graph",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(fintrac_risk_score_bucket[5m]))"
        }]
      },
      {
        "title": "FINTRAC Submission Success Rate",
        "type": "stat",
        "targets": [{
          "expr": "rate(fintrac_submission_success_total[1h]) / rate(fintrac_submission_attempt_total[1h])"
        }]
      },
      {
        "title": "Structuring Alerts (24h)",
        "type": "alert-list",
        "alertName": "StructuringPatternDetected"
      }
    ]
  }
}
```

---

## 12. Testing Strategy

```python
# test_fintrac_compliance.py
import pytest
from pytest_mock import Mocker
from freezegun import freeze_time
from datetime import timedelta

class TestFINTRACCompliance:
    """
    Comprehensive compliance testing suite
    """
    
    @pytest.mark.asyncio
    async def test_lctr_threshold_trigger(self, client, db):
        """Test Large Cash Transaction Report threshold"""
        
        response = await client.post(
            "/fintrac/applications/test-id/report-transaction",
            json={
                "amount": "10001.00",
                "currency": "CAD",
                "transaction_date": "2024-01-15"
            }
        )
        
        assert response.status_code == 201
        report = await db.get(FintracReport, response.json()["report_id"])
        assert report.report_type == "large_cash_transaction"
        assert report.amount == Decimal("10001.00")
    
    @pytest.mark.asyncio
    @freeze_time("2024-01-15 12:00:00")
    async def test_structuring_detection_24h_window(self, client, db, redis):
        """Test smurfing detection with sliding window"""
        
        # Submit 3 transactions just under threshold within 24h
        for i in range(3):
            await client.post(
                "/fintrac/applications/test-id/report-transaction",
                json={
                    "amount": "9999.00",
                    "currency": "CAD",
                    "transaction_date": f"2024-01-15"
                }
            )
        
        # Check Redis window
        window_key = "txn_window:test-id"
        txns = await redis.zrange(window_key, 0, -1)
        assert len(txns) == 3
        
        # Verify suspicious report created
        suspicious_reports = await db.execute(
            select(FintracReport).where(
                FintracReport.report_type == "suspicious_transaction",
                FintracReport.application_id == "test-id"
            )
        )
        assert suspicious_reports.scalar_one() is not None
    
    @pytest.mark.asyncio
    async def test_enhanced_due_diligence_trigger(self, client):
        """Test EDD triggers for PEP/HIO/high-risk"""
        
        test_cases = [
            {"is_pep": True, "expected_edd": True},
            {"is_hio": True, "expected_edd": True},
            {"risk_level": "high", "expected_edd": True},
            {"risk_level": "low", "expected_edd": False}
        ]
        
        for case in test_cases:
            response = await client.post(
                "/fintrac/applications/test-id/verify-identity",
                json={
                    "verification_method": "in_person",
                    "id_type": "passport",
                    "id_number": "TEST123",
                    "id_expiry_date": "2025-01-01",
                    "id_issuing_province": "ON",
                    **case
                }
            )
            
            assert response.json()["requires_edd"] == case["expected_edd"]
    
    @pytest.mark.asyncio
    async def test_immutable_audit_trail(self, db, audit_logger):
        """Test audit log tamper detection"""
        
        # Create audit entries
        entry1 = await audit_logger.log_action(
            table_name="test_table",
            record_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            action="INSERT",
            new_values={"field": "value1"},
            user_id=UUID("123e4567-e89b-12d3-a456-426614174001")
        )
        
        entry2 = await audit_logger.log_action(
            table_name="test_table",
            record_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            action="UPDATE",
            old_values={"field": "value1"},
            new_values={"field": "value2"},
            user_id=UUID("123e4567-e89b-12d3-a456-426614174001")
        )
        
        # Verify hash chain
        assert entry2.previous_hash == entry1.current_hash
        
        # Verify integrity
        is_intact = await audit_logger.verify_chain_integrity(
            table_name="test_table",
            record_id=UUID("123e4567-e89b-12d3-a456-426614174000")
        )
        assert is_intact is True
        
        # Simulate tampering
        entry2.new_values = {"field": "tampered"}
        await db.commit()
        
        # Verify integrity fails
        is_intact = await audit_logger.verify_chain_integrity(
            table_name="test_table",
            record_id=UUID("123e4567-e89b-12d3-a456-426614174000")
        )
        assert is_intact is False
    
    @pytest.mark.asyncio
    async def test_soft_delete_retention(self, client, db):
        """Test 5-year soft delete retention policy"""
        
        # Create and soft delete verification
        verification = await create_test_verification(db)
        
        await client.delete(
            f"/fintrac/verifications/{verification.id}",
            json={"reason": "test deletion"}
        )
        
        # Verify soft delete record created
        soft_delete = await db.execute(
            select(FintracSoftDelete)
            .where(FintracSoftDelete.record_id == verification.id)
        )
        record = soft_delete.scalar_one()
        
        assert record.retention_until == datetime.utcnow() + timedelta(days=365*5)
        assert record.data_snapshot is not None
        
        # Verify not hard deleted
        still_exists = await db.get(FintracVerification, verification.id)
        assert still_exists.deleted_at is not None
```

---

## 13. Configuration Management

```python
# config.py
from pydantic_settings import BaseSettings
from decimal import Decimal

class FINTRACConfig(BaseSettings):
    """
    Centralized configuration with validation
    Supports environment-specific overrides
    """
    
    # Thresholds
    LCTR_THRESHOLD: Decimal = Decimal("10000.00")
    STRUCTURING_WINDOW_HOURS: int = 24
    STRUCTURING_COUNT_THRESHOLD: int = 3
    
    # Risk scoring weights
    RISK_WEIGHT_PEP: float = 30.0
    RISK_WEIGHT_HIO: float = 25.0
    RISK_WEIGHT_GEOGRAPHIC: float = 15.0
    RISK_WEIGHT_AMOUNT: float = 10.0
    
    # External APIs
    FINTRAC_ESTR_URL: str = "https://api.fintrac-canafe.gc.ca/estr/v2"
    FINTRAC_SUBMITTER_ID: str
    FINTRAC_CLIENT_CERT_PATH: str = "/secrets/fintrac.pem"
    
    # PEP/HIO Providers
    WORLDCHECK_API_URL: str
    WORLDCHECK_API_KEY: str
    LEXISNEXIS_API_URL: str
    LEXISNEXIS_CLIENT_ID: str
    
    # Retention
    RETENTION_YEARS: int = 5
    
    # Security
    ENCRYPTION_KEY_ROTATION_DAYS: int = 365
    AUDIT_LOG_PARTITION_MONTHS: int = 1
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# config_loader.py
def load_environment_config(env: str) -> FINTRACConfig:
    """
    Load environment-specific configuration
    """
    
    config_files = {
        "development": ".env.dev",
        "staging": ".env.staging",
        "production": ".env.prod"
    }
    
    os.environ["ENV_FILE"] = config_files.get(env, ".env.dev")
    return FINTRACConfig()
```

---

## 14. Runbook & Operational Procedures

```markdown
# FINTRAC Compliance Module Runbook

## Daily Operations

### 1. Watchlist Sync Verification
```bash
# Check last successful sync
kubectl logs -l app=pep-hio-sync --since=24h | grep "sync completed"

# Verify Redis cache population
kubectl exec -it redis-cli -- zcard pep_hio:index
```

### 2. FINTRAC Submission Queue Monitoring
```bash
# Check pending reports
kubectl exec -it postgres -- psql -c "SELECT count(*) FROM fintrac_reports WHERE status='draft'"

# View submission metrics
curl http://prometheus:9090/api/v1/query?query=fintrac_submission_attempt_total
```

### 3. Audit Log Integrity Check
```python
# Run integrity verification script
python scripts/verify_audit_chain.py --table fintrac_verifications --since 24h
```

## Incident Response

### Scenario: FINTRAC API Outage
1. **Detection**: Alert fires when `fintrac_submission_success_rate < 0.95`
2. **Response**:
   ```bash
   # Enable circuit breaker
   kubectl patch configmap fintrac-config --patch '{"data":{"FINTRAC_API_ENABLED":"false"}}'
   
   # Queue reports for retry
   kubectl exec -it fintrac-reporting -- python scripts/requeue_reports.py
   ```
3. **Recovery**: Auto-retry when API health check passes

### Scenario: PEP/HIO Sync Failure
1. **Detection**: `watchlist_sync_last_success > 24h`
2. **Response**:
   ```bash
   # Rollback to previous version
   kubectl exec -it pep-hio-sync -- npm run rollback-watchlist
   
   # Manual sync trigger
   kubectl exec -it pep-hio-sync -- npm run force-sync
   ```

### Scenario: Structuring Alert
1. **Detection**: Real-time alert from Transaction Monitor
2. **Response**:
   ```python
   # Auto-create suspicious transaction report
   await reporting_service.create_str_report(
       application_id=alert.application_id,
       reason="structuring_pattern",
       transactions=alert.transactions
   )
   
   # Notify compliance team
   await slack_notifier.send(
       channel="#compliance-alerts",
       message=f"Structuring detected: {alert.application_id}"
   )
   ```

## Compliance Reporting

### Monthly FINTRAC Metrics Report
```sql
-- Generate compliance report
SELECT 
    DATE_TRUNC('month', verified_at) as month,
    COUNT(*) as total_verifications,
    SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) as high_risk_count,
    SUM(CASE WHEN is_pep = TRUE THEN 1 ELSE 0 END) as pep_count,
    SUM(CASE WHEN is_hio = TRUE THEN 1 ELSE 0 END) as hio_count,
    COUNT(DISTINCT application_id) as unique_applications,
    AVG(risk_score) as avg_risk_score
FROM fintrac_verifications
WHERE deleted_at IS NULL
GROUP BY DATE_TRUNC('month', verified_at)
ORDER BY month DESC;
```

### Annual Key Rotation
```bash
# Schedule rotation
kubectl create job fintrac-key-rotation \
  --image=onlendhub/fintrac-key-rotator:v2.1 \
  --schedule="0 0 1 1 *" \
  --env="DRY_RUN=false"
```

---

## 15. Missing Details Resolution

### ✅ PEP/HIO List Integration
- **Automated daily sync** from World-Check and LexisNexis
- **Redis in-memory index** for sub-100ms screening
- **Bloom filter** for fast negative matches
- **Fuzzy matching** with Levenshtein distance for name variations

### ✅ Risk Scoring Algorithm
- **Weighted multi-factor model** (PEP: 30%, HIO: 25%, Geography: 15%)
- **Configurable thresholds** via `config.py`
- **Versioned scoring** allows A/B testing and regulatory updates
- **Real-time recalculation** on PEP list updates

### ✅ FINTRAC Submission API
- **ESTR v2.0 XML format** with digital signing
- **Idempotent submissions** using content-based keys
- **Circuit breaker pattern** for resilience
- **Retry queue** with exponential backoff
- **WORM storage** of all submissions for audit

### ✅ Transaction Monitoring Thresholds
- **Configurable LCTR threshold** (default: $10,000 CAD)
- **Sliding window algorithm** for structuring detection
- **ML-based anomaly detection** (optional enhancement)
- **Alert tuning** via `STRUCTURING_COUNT_THRESHOLD`

### ✅ Audit Trail Requirements
- **Immutable hash chaining** prevents tampering
- **Row-level security** in PostgreSQL
- **Monthly partitioning** for performance
- **WORM archival** to S3 Glacier
- **Real-time integrity verification** API

---

## 16. Performance & Scalability Targets

| Metric | Target | Implementation |
|--------|--------|----------------|
| **PEP Screening Latency** | < 100ms | Redis in-memory index |
| **Risk Score Calculation** | < 200ms | Async multi-factor evaluation |
| **Transaction Processing** | 1000 TPS | Kafka event streaming |
| **FINTRAC Submission** | < 5s | HTTP/2 connection pooling |
| **Audit Log Query** | < 1s | Monthly partitioning |
| **Database Encryption** | < 10ms overhead | Vault Transit + local Fernet |

---

## 17. Regulatory Compliance Checklist

- [ ] **PCMLTFA Section 6.1**: Identity verification methods implemented
- [ ] **PCMLTFA Section 7**: Large cash transaction reporting (> $10,000)
- [ ] **PCMLTFA Section 7.1**: Suspicious transaction reporting with indicators
- [ ] **PCMLTFA Section 11.1**: PEP/HIO determination and EDD
- [ ] **PCMLTFA Section 73**: 5-year record retention with soft-delete
- [ ] **FINTRAC Guideline 6**: 24-hour rule for structuring detection
- [ ] **PIPEDA**: Encryption of PII at rest and in transit
- [ ] **OSFI Guideline B-8**: Risk-based approach with scoring

---

**Architecture Version**: 2.1  
**Last Updated**: 2024-01-15  
**Compliance Framework**: PCMLTFA 2023 Amendments