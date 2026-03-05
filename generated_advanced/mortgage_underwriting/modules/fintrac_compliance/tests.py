--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
import asyncio

# Mocking the application structure for testing purposes
# In a real scenario, these would be imported from the actual modules
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.fintrac.models import FintracTransaction
from mortgage_underwriting.modules.fintrac.routes import router
from mortgage_underwriting.modules.fintrac.schemas import FintracTransactionCreate

# Database Setup (Using SQLite for test isolation)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/fintrac", tags=["fintrac"])
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_fintrac_payload() -> dict:
    return {
        "applicant_id": "test-applicant-123",
        "amount": "5000.00",
        "currency": "CAD",
        "transaction_type": "deposit",
        "entity_type": "individual"
    }

@pytest.fixture
def large_cash_payload() -> dict:
    return {
        "applicant_id": "test-applicant-456",
        "amount": "12000.00",
        "currency": "CAD",
        "transaction_type": "cash_deposit",
        "entity_type": "individual"
    }

@pytest.fixture
def invalid_amount_payload() -> dict:
    return {
        "applicant_id": "test-applicant-789",
        "amount": "-100.00",
        "currency": "CAD",
        "transaction_type": "deposit",
        "entity_type": "individual"
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.modules.fintrac.models import FintracTransaction
from mortgage_underwriting.modules.fintrac.schemas import FintracTransactionCreate
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = MagicMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return FintracService(mock_db)

    @pytest.mark.asyncio
    async def test_create_transaction_success(self, service, mock_db):
        payload = FintracTransactionCreate(
            applicant_id="app-123",
            amount=Decimal("5000.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )

        result = await service.create_transaction(payload)

        assert result.applicant_id == "app-123"
        assert result.amount == Decimal("5000.00")
        assert result.is_large_cash_reportable is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_large_cash_transaction_flagged(self, service, mock_db):
        # Boundary test: Exactly 10000.00
        payload_boundary = FintracTransactionCreate(
            applicant_id="app-999",
            amount=Decimal("10000.00"),
            currency="CAD",
            transaction_type="cash_deposit",
            entity_type="individual"
        )
        result_boundary = await service.create_transaction(payload_boundary)
        assert result_boundary.is_large_cash_reportable is True

        # Test: Above 10000.00
        payload_high = FintracTransactionCreate(
            applicant_id="app-888",
            amount=Decimal("15000.50"),
            currency="CAD",
            transaction_type="cash_deposit",
            entity_type="individual"
        )
        result_high = await service.create_transaction(payload_high)
        assert result_high.is_large_cash_reportable is True

    @pytest.mark.asyncio
    async def test_create_non_cash_transaction_not_flagged(self, service, mock_db):
        # Even if > 10k, if it's not cash/physical, it might not be flagged as "Large Cash" 
        # depending on specific business logic, but here we test the cash flag specifically
        payload = FintracTransactionCreate(
            applicant_id="app-777",
            amount=Decimal("50000.00"),
            currency="CAD",
            transaction_type="wire_transfer", # Not cash
            entity_type="business"
        )
        result = await service.create_transaction(payload)
        # Assuming logic only flags cash transactions > 10k for this specific flag
        assert result.is_large_cash_reportable is False

    @pytest.mark.asyncio
    async def test_create_transaction_invalid_amount_raises_error(self, service, mock_db):
        with pytest.raises(ValueError) as exc_info:
            payload = FintracTransactionCreate(
                applicant_id="app-123",
                amount=Decimal("-500.00"),
                currency="CAD",
                transaction_type="deposit",
                entity_type="individual"
            )
            await service.create_transaction(payload)
        
        assert "Amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_transaction_zero_amount_raises_error(self, service, mock_db):
        with pytest.raises(ValueError) as exc_info:
            payload = FintracTransactionCreate(
                applicant_id="app-123",
                amount=Decimal("0.00"),
                currency="CAD",
                transaction_type="deposit",
                entity_type="individual"
            )
            await service.create_transaction(payload)
        
        assert "Amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_audit_fields_set_on_creation(self, service, mock_db):
        payload = FintracTransactionCreate(
            applicant_id="app-123",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )

        result = await service.create_transaction(payload)

        assert result.created_at is not None
        assert result.created_by is not None # Assuming service sets this, e.g., "system" or user context
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_log_identity_verification(self, service, mock_db):
        with patch("mortgage_underwriting.modules.fintrac.services.logger") as mock_logger:
            payload = FintracTransactionCreate(
                applicant_id="app-123",
                amount=Decimal("100.00"),
                currency="CAD",
                transaction_type="deposit",
                entity_type="individual"
            )
            
            await service.create_transaction(payload)
            
            # Verify logging occurred for FINTRAC compliance
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert "Identity verification" in str(call_args) or "FINTRAC" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_transaction_by_id(self, service, mock_db):
        # Setup mock result
        mock_transaction = FintracTransaction(
            id=1,
            applicant_id="app-123",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )
        
        # Mock the execute/scalar chain for get
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_transaction
        mock_db.execute.return_value = mock_result

        result = await service.get_transaction(1)

        assert result is not None
        assert result.id == 1
        assert result.applicant_id == "app-123"

    @pytest.mark.asyncio
    async def test_get_transaction_not_found_returns_none(self, service, mock_db):
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_transaction(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_db_integrity_error_handling(self, service, mock_db):
        mock_db.commit.side_effect = IntegrityError("mock", "mock", "mock")
        
        payload = FintracTransactionCreate(
            applicant_id="app-123",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )

        with pytest.raises(AppException) as exc_info:
            await service.create_transaction(payload)
        
        assert "Database error" in str(exc_info.value)
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.fintrac.models import FintracTransaction

@pytest.mark.integration
class TestFintracRoutes:

    @pytest.mark.asyncio
    async def test_create_transaction_success(self, client: AsyncClient, valid_fintrac_payload):
        response = await client.post("/api/v1/fintrac/transactions", json=valid_fintrac_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["applicant_id"] == valid_fintrac_payload["applicant_id"]
        assert data["amount"] == valid_fintrac_payload["amount"]
        assert data["currency"] == "CAD"
        assert data["is_large_cash_reportable"] is False
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_large_cash_transaction_auto_flagged(self, client: AsyncClient, large_cash_payload):
        response = await client.post("/api/v1/fintrac/transactions", json=large_cash_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["is_large_cash_reportable"] is True
        assert Decimal(data["amount"]) == Decimal("12000.00")

    @pytest.mark.asyncio
    async def test_create_transaction_validation_error_negative_amount(self, client: AsyncClient, invalid_amount_payload):
        response = await client.post("/api/v1/fintrac/transactions", json=invalid_amount_payload)
        
        assert response.status_code == 422 # Unprocessable Entity for Pydantic validation
        errors = response.json().get("detail", [])
        assert any("greater than 0" in str(err).lower() or "positive" in str(err).lower() for err in errors)

    @pytest.mark.asyncio
    async def test_create_transaction_missing_field(self, client: AsyncClient):
        incomplete_payload = {
            "applicant_id": "test",
            "amount": "100.00"
            # Missing currency, transaction_type, entity_type
        }
        response = await client.post("/api/v1/fintrac/transactions", json=incomplete_payload)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_transaction_by_id(self, client: AsyncClient, db_session, valid_fintrac_payload):
        # 1. Create a transaction directly in DB
        new_trans = FintracTransaction(
            applicant_id=valid_fintrac_payload["applicant_id"],
            amount=Decimal(valid_fintrac_payload["amount"]),
            currency=valid_fintrac_payload["currency"],
            transaction_type=valid_fintrac_payload["transaction_type"],
            entity_type=valid_fintrac_payload["entity_type"],
            is_large_cash_reportable=False
        )
        db_session.add(new_trans)
        await db_session.commit()
        await db_session.refresh(new_trans)

        # 2. Fetch via API
        response = await client.get(f"/api/v1/fintrac/transactions/{new_trans.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == new_trans.id
        assert data["applicant_id"] == valid_fintrac_payload["applicant_id"]

    @pytest.mark.asyncio
    async def test_get_transaction_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/fintrac/transactions/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_list_transactions(self, client: AsyncClient, db_session):
        # Create multiple transactions
        trans1 = FintracTransaction(
            applicant_id="app-1", amount=Decimal("100.00"), currency="CAD",
            transaction_type="deposit", entity_type="individual", is_large_cash_reportable=False
        )
        trans2 = FintracTransaction(
            applicant_id="app-2", amount=Decimal("200.00"), currency="CAD",
            transaction_type="deposit", entity_type="individual", is_large_cash_reportable=False
        )
        db_session.add_all([trans1, trans2])
        await db_session.commit()

        response = await client.get("/api/v1/fintrac/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        ids = [item["id"] for item in data]
        assert trans1.id in ids
        assert trans2.id in ids

    @pytest.mark.asyncio
    async def test_immutable_audit_trail_on_retrieval(self, client: AsyncClient, db_session, valid_fintrac_payload):
        # Create transaction
        create_resp = await client.post("/api/v1/fintrac/transactions", json=valid_fintrac_payload)
        trans_id = create_resp.json()["id"]
        
        # Get transaction
        get_resp = await client.get(f"/api/v1/fintrac/transactions/{trans_id}")
        data = get_resp.json()
        
        # Ensure created_at is present and immutable logic is implied (cannot update via POST)
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        
        # Verify persistence in DB
        db_record = await db_session.get(FintracTransaction, trans_id)
        assert db_record.created_at is not None
        assert db_record.created_by is not None

    @pytest.mark.asyncio
    async def test_large_cash_boundary_conditions(self, client: AsyncClient):
        # Test 9999.99 (Not reportable)
        payload_under = {
            "applicant_id": "bound-1", "amount": "9999.99", "currency": "CAD",
            "transaction_type": "cash_deposit", "entity_type": "individual"
        }
        resp_under = await client.post("/api/v1/fintrac/transactions", json=payload_under)
        assert resp_under.json()["is_large_cash_reportable"] is False

        # Test 10000.00 (Reportable)
        payload_exact = {
            "applicant_id": "bound-2", "amount": "10000.00", "currency": "CAD",
            "transaction_type": "cash_deposit", "entity_type": "individual"
        }
        resp_exact = await client.post("/api/v1/fintrac/transactions", json=payload_exact)
        assert resp_exact.json()["is_large_cash_reportable"] is True

        # Test 10000.01 (Reportable)
        payload_over = {
            "applicant_id": "bound-3", "amount": "10000.01", "currency": "CAD",
            "transaction_type": "cash_deposit", "entity_type": "individual"
        }
        resp_over = await client.post("/api/v1/fintrac/transactions", json=payload_over)
        assert resp_over.json()["is_large_cash_reportable"] is True
```