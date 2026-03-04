# Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Database Migrations & Seed Data Architecture

## Migration Strategy Design

### 1. **Alembic Configuration**
```bash
# Initialize Alembic with async support
alembic init -t async migrations

# alembic.ini configuration
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+asyncpg://%(DB_USER)s:%(DB_PASS)s@%(DB_HOST)s:%(DB_PORT)s/%(DB_NAME)s?async_fallback=true
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s
truncate_slug_length = 40
revision_environment = true

# env.py modifications for async engine
```

### 2. **Module-Based Migration Structure (12 Total)**

```python
# migrations/versions/
├── 20240115_100000_users_module.py          # Auth & RBAC
├── 20240115_110000_lenders_module.py        # Lender entities
├── 20240115_120000_products_module.py       # Mortgage products
├── 20240115_130000_clients_module.py        # Borrower profiles
├── 20240115_140000_applications_module.py   # Application header
├── 20240115_150000_documents_module.py      # Document storage
├── 20240115_160000_credit_bureau_module.py  # Credit data
├── 20240115_170000_property_module.py       # Property valuation
├── 20240115_180000_underwriting_module.py   # UW engine results
├── 20240115_190000_workflow_module.py       # State management
├── 20240115_200000_audit_module.py          # Compliance logging
└── 20240115_210000_notifications_module.py  # Alert system
```

---

## 3. **Migration Module Templates**

### **Base Migration Template (Reversible)**
```python
# migrations/templates/module_template.py
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

def upgrade() -> None:
    # === CREATE TABLE(S) ===
    op.create_table(
        'table_name',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        # Module-specific columns
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
        # Audit fields
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
    )
    
    # === CREATE INDEXES ===
    op.create_index('idx_table_name_active', 'table_name', ['is_active'])
    
    # === CREATE FOREIGN KEYS ===
    op.create_foreign_key(
        'fk_table_name_created_by',
        'table_name', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL'
    )
    
    # === CREATE ENUM TYPES ===
    op.execute("CREATE TYPE application_status AS ENUM ('draft', 'submitted', 'under_review', 'approved', 'declined', 'conditional')")

def downgrade() -> None:
    # === DROP IN REVERSE ORDER ===
    op.drop_constraint('fk_table_name_created_by', 'table_name', type_='foreignkey')
    op.drop_index('idx_table_name_active', table_name='table_name')
    op.drop_table('table_name')
    op.execute("DROP TYPE IF EXISTS application_status")
```

---

## 4. **Seed Data Implementation Strategy**

### **Environment-Aware Seeding System**

```python
# app/db/seed_manager.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.models import User, Lender, Product, Application

class SeedManager:
    def __init__(self, env: str = "development"):
        self.env = env
        self.seed_data = self._load_seed_config()
    
    async def seed_all(self, db: AsyncSession):
        """Idempotent seeding with verification"""
        try:
            await self._seed_users(db)
            await self._seed_lenders(db)
            await self._seed_products(db)
            await self._seed_sample_application(db)
            await self._seed_audit_data(db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise SeedError(f"Seeding failed: {e}")
    
    async def verify_seed(self, db: AsyncSession) -> dict:
        """Verify seed data integrity"""
        return {
            "users": await db.scalar(select(func.count()).select_from(User)),
            "lenders": await db.scalar(select(func.count()).select_from(Lender)),
            "products": await db.scalar(select(func.count()).select_from(Product)),
        }
```

### **Password Security Implementation**
```python
# app/core/security.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash passwords using Argon2id (NIST recommended)"""
    return pwd_context.hash(password)

# NEVER store plaintext passwords in migrations
# Store hashes in environment variables or secrets manager
```

---

## 5. **Complete Seed Data Specification**

### **A. User Seed Data**
```python
# app/db/seeds/users.py
USERS = [
    {
        "email": "admin@mortgage-uw.local",
        "hashed_password": get_password_hash("Admin@12345"),  # Runtime hash
        "role": "admin",
        "is_active": True,
        "mfa_enabled": False,
    },
    {
        "email": "broker@mortgage-uw.local",
        "hashed_password": get_password_hash("Broker@12345"),
        "role": "broker",
        "is_active": True,
        "license_number": "MB-2024-001",
    },
    {
        "email": "client@mortgage-uw.local",
        "hashed_password": get_password_hash("Client@12345"),
        "role": "client",
        "is_active": True,
        "credit_score": 750,
    }
]
```

### **B. Lender & Product Seed Data**
```python
# app/db/seeds/lenders.py
from decimal import Decimal

LENDERS = [
    {
        "name": "Royal Bank of Canada",
        "code": "RBC",
        "type": "bank",
        "is_active": True,
        "products": [
            {
                "name": "5-Year Fixed Rate Mortgage",
                "rate_type": "fixed",
                "term_years": 5,
                "interest_rate": Decimal("5.24"),
                "rate_bps": 524,
                "amortization_max_years": 30,
                "insurance_required": False,
            },
            {
                "name": "5-Year Variable Rate Mortgage",
                "rate_type": "variable",
                "term_years": 5,
                "interest_rate": Decimal("6.15"),
                "rate_bps": 615,
                "amortization_max_years": 30,
                "insurance_required": False,
            }
        ]
    },
    # ... TD, BMO, Scotiabank, CIBC with similar structure
]

# Baseline rates as of Q1 2024 (CMHC benchmark)
# Use Decimal for precision, store in basis points for calculations
```

---

## 6. **Addressing Missing Details**

### **A. Lender Product Rates Baseline**
```python
# app/db/seeds/rate_baseline.py
"""
Rate Structure:
- Prime Rate: 7.20% (Bank of Canada Jan 2024)
- Fixed rates: Prime - discount (varies by lender)
- Variable rates: Prime + premium
- Stored as DECIMAL(5,2) and INTEGER basis points
"""

RATE_BASELINES = {
    "prime_rate": Decimal("7.20"),
    "stress_test_rate": Decimal("8.20"),  # OSFI B-20 guideline
    "lender_spreads": {
        "RBC": {"fixed_discount": Decimal("1.96"), "variable_premium": Decimal("-1.05")},
        "TD": {"fixed_discount": Decimal("1.99"), "variable_premium": Decimal("-1.00")},
        # ...
    }
}
```

### **B. Sample Application Scenarios**
```python
# app/db/seeds/sample_applications.py
SAMPLE_APPLICATIONS = {
    "approved": {
        "property_value": Decimal("750000"),
        "loan_amount": Decimal("600000"),
        "ltv": Decimal("80.0"),
        "gdsr": Decimal("32.1"),
        "tdsr": Decimal("39.8"),
        "uw_decision": "approved",
        "conditions": ["proof_of_insurance", "appraisal_confirmation"]
    },
    "declined": {
        "property_value": Decimal("500000"),
        "loan_amount": Decimal("475000"),
        "ltv": Decimal("95.0"),
        "gdsr": Decimal("45.2"),
        "tdsr": Decimal("52.1"),
        "uw_decision": "declined",
        "decline_reasons": ["exceeds_tdsr_threshold", "insufficient_credit_history"]
    },
    "conditional": {
        "property_value": Decimal("650000"),
        "loan_amount": Decimal("520000"),
        "ltv": Decimal("80.0"),
        "gdsr": Decimal("35.5"),
        "tdsr": Decimal("42.0"),
        "uw_decision": "conditional",
        "conditions": ["reduce_loan_to_500k", "add_cosigner", "pay_down_credit_cards"]
    }
}
```

---

## 7. **Environment-Specific Seed Variations**

```python
# app/db/seeds/config.py
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

def get_seed_config(env: Environment):
    return {
        Environment.DEVELOPMENT: {
            "sample_data_size": "full",
            "include_test_accounts": True,
            "overwrite_existing": True,
            "stress_test_users": 100,
        },
        Environment.STAGING: {
            "sample_data_size": "medium",
            "include_test_accounts": True,
            "overwrite_existing": False,
            "stress_test_users": 1000,
        },
        Environment.PRODUCTION: {
            "sample_data_size": "minimal",
            "include_test_accounts": False,
            "overwrite_existing": False,
            "stress_test_users": 0,
            "require_mfa": True,
        }
    }[env]
```

---

## 8. **Migration Rollback Testing Strategy**

```python
# tests/db/test_migrations.py
import pytest
from alembic.config import Config
from alembic.command import upgrade, downgrade
from sqlalchemy.engine import Engine

class TestMigrationRounds:
    def test_migration_rollback_cycle(self, alembic_engine: Engine):
        """Test each migration can upgrade/downgrade cleanly"""
        config = Config("alembic.ini")
        
        # Get all revisions
        revisions = self._get_all_revisions(config)
        
        for rev in revisions:
            # Upgrade to this revision
            upgrade(config, rev)
            assert self._check_schema_consistency(alembic_engine)
            
            # Downgrade back
            downgrade(config, rev)
            assert self._check_schema_consistency(alembic_engine)
    
    def test_data_preservation_on_rollback(self, async_db: AsyncSession):
        """Verify seed data persists after downgrade/upgrade cycle"""
        seed_manager = SeedManager(env="test")
        await seed_manager.seed_all(async_db)
        
        initial_counts = await seed_manager.verify_seed(async_db)
        
        # Perform downgrade then upgrade
        downgrade(config, "base")
        upgrade(config, "head")
        
        final_counts = await seed_manager.verify_seed(async_db)
        assert initial_counts == final_counts
```

---

## 9. **Stress Test Data Generation**

```python
# app/db/seeds/stress_test.py
from faker import Faker
from app.models import Client, Application

class StressTestDataGenerator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.fake = Faker('en_CA')
    
    async def generate_bulk_data(self, num_clients: int = 10000):
        """Generate compliant stress test data"""
        batch_size = 1000
        
        for i in range(0, num_clients, batch_size):
            clients = [
                Client(
                    first_name=self.fake.first_name(),
                    last_name=self.fake.last_name(),
                    sin=self.fake.ssn().replace('-', ''),
                    credit_score=self.fake.random_int(600, 850),
                    # ...
                )
                for _ in range(batch_size)
            ]
            self.db.add_all(clients)
        
        await self.db.commit()
```

---

## 10. **Best Practices Implementation**

### **A. Decimal Precision Pattern**
```python
# app/models/base.py
from sqlalchemy import Numeric
from decimal import Decimal

class FinancialMixin:
    """Mixin for financial precision"""
    amount = sa.Column(Numeric(precision=15, scale=2), nullable=False)
    rate = sa.Column(Numeric(precision=5, scale=4), nullable=False)  # 0.1234%
    
    @property
    def amount_decimal(self) -> Decimal:
        return Decimal(str(self.amount))
```

### **B. Audit Logging Pattern**
```python
# app/models/audit.py
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = sa.Column(UUID, primary_key=True)
    table_name = sa.Column(sa.String(64), index=True)
    record_id = sa.Column(UUID, index=True)
    action = sa.Column(sa.Enum('INSERT', 'UPDATE', 'DELETE', 'SELECT'))
    changed_by = sa.Column(UUID, sa.ForeignKey('users.id'))
    old_values = sa.Column(JSONB)
    new_values = sa.Column(JSONB)
    timestamp = sa.Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Trigger-based auditing via PostgreSQL
    __table_args__ = (
        sa.Index('idx_audit_table_record', 'table_name', 'record_id'),
    )
```

### **C. Workflow Versioning**
```python
# app/models/workflow.py
class ApplicationState(Base):
    """Immutable state history"""
    __tablename__ = "application_states"
    
    id = sa.Column(UUID, primary_key=True)
    application_id = sa.Column(UUID, sa.ForeignKey('applications.id'))
    status = sa.Column(application_status_enum, nullable=False)
    version = sa.Column(sa.Integer, nullable=False)
    effective_from = sa.Column(TIMESTAMP(timezone=True))
    effective_to = sa.Column(TIMESTAMP(timezone=True))
    
    __table_args__ = (
        sa.UniqueConstraint('application_id', 'version'),
        sa.Index('idx_state_version', 'application_id', 'version', unique=True),
    )
```

---

## 11. **Execution Commands**

```bash
# Development seeding
python -m app.db.seed_manager --env=development --seed

# Staging with verification
python -m app.db.seed_manager --env=staging --seed --verify

# Production minimal seed (admin only)
python -m app.db.seed_manager --env=production --seed-minimal

# Migration testing
pytest tests/db/test_migrations.py -v

# Rollback test
alembic downgrade -1 && alembic upgrade head
```

---

## 12. **Directory Structure**

```
app/
├── db/
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── seeds/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── users.py
│   │   ├── lenders.py
│   │   ├── products.py
│   │   ├── sample_applications.py
│   │   ├── rate_baseline.py
│   │   └── stress_test.py
│   └── seed_manager.py
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── user.py
│   ├── lender.py
│   └── ...
└── core/
    └── security.py
```

This architecture ensures **regulatory compliance**, **data integrity**, and **operational safety** for the Canadian mortgage underwriting system while providing comprehensive testing capabilities.