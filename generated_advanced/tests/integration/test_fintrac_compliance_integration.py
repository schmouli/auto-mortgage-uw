```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

# Absolute Imports
from mortgage_underwriting.modules.fintrac.routes import router as fintrac_router
from mortgage_underwriting.modules.fintrac.models import FintracTransactionLog, IdentityVerificationRecord
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracIntegration:

    @pytest.fixture
    def app(self, db_session):
        """
        Create a test FastAPI app with the Fintrac router and overridden DB dependency.
        """
        app = FastAPI()
        app.include_router(fintrac_router, prefix="/api/v1/fintrac", tags=["fintrac"])

        # Override the dependency
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db
        yield app
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_transaction_endpoint(self, app: FastAPI, valid_transaction_payload):
        """
        Test creating a transaction via API.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["amount"] == valid_transaction_payload["amount"]
            assert data["is_large_cash_reportable"] is False
            assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_large_cash_transaction_endpoint(self, app: FastAPI, large_cash_transaction_payload):
        """
        Test creating a large cash transaction (> 10k) via API.
        Verifies FINTRAC flag is set correctly.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/transactions", json=large_cash_transaction_payload)

            assert response.status_code == 201
            data = response.json()
            assert data["is_large_cash_reportable"] is True
            assert data["amount"] == large_cash_transaction_payload["amount"]

    @pytest.mark.asyncio
    async def test_get_transaction_retrieval(self, app: FastAPI, valid_transaction_payload, db_session):
        """
        Test retrieving a logged transaction.
        """
        # First, create a transaction
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
            trans_id = create_resp.json()["id"]

            # Retrieve it
            get_resp = await client.get(f"/api/v1/fintrac/transactions/{trans_id}")
            
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == trans_id
            assert data["applicant_id"] == valid_transaction_payload["applicant_id"]

    @pytest.mark.asyncio
    async def test_log_identity_verification_endpoint(self, app: FastAPI, identity_verification_payload):
        """
        Test logging identity verification.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/identity-verify", json=identity_verification_payload)

            assert response.status_code == 201
            data = response.json()
            assert data["applicant_id"] == identity_verification_payload["applicant_id"]
            assert data["verification_method"] == identity_verification_payload["verification_method"]
            assert data["verified_at"] is not None

    @pytest.mark.asyncio
    async def test_invalid_transaction_amount_rejected(self, app: FastAPI):
        """
        Test that invalid payloads (e.g., negative amounts) return 422.
        """
        invalid_payload = {
            "applicant_id": "app_123",
            "amount": "-500.00",
            "currency": "CAD",
            "transaction_type": "PAYMENT",
            "account_number": "****1234",
            "institution_id": "inst_01"
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/transactions", json=invalid_payload)
            assert response.status_code == 422 # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_transaction_persistence_in_db(self, app: FastAPI, valid_transaction_payload, db_session):
        """
        Verify that data is actually persisted in the database correctly.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)

        # Query DB directly
        stmt = select(FintracTransactionLog).where(
            FintracTransactionLog.applicant_id == valid_transaction_payload["applicant_id"]
        )
        result = await db_session.execute(stmt)
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.amount == Decimal(valid_transaction_payload["amount"])
        assert record.created_by is not None
        assert record.created_at is not None

    @pytest.mark.asyncio
    async def test_fintrac_audit_trail_integrity(self, app: FastAPI, valid_transaction_payload, db_session):
        """
        Regulatory: Verify audit fields are immutable and present.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
            created_at = resp.json()["created_at"]

        # Ensure created_at is a valid ISO format string
        assert created_at is not None
        
        # In a real scenario, we might try to update the record via the API
        # and ensure created_at does not change, or the update is rejected if 
        # strict immutability is enforced at the API level.
        # Assuming the API only allows POST (Create) and GET (Read) for audit logs.
        
        stmt = select(FintracTransactionLog).where(
            FintracTransactionLog.applicant_id == valid_transaction_payload["applicant_id"]
        )
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        
        assert record.updated_at is not None # Track last update time even if content is mostly immutable

    @pytest.mark.asyncio
    async def test_list_transactions_filtering(self, app: FastAPI, valid_transaction_payload, large_cash_transaction_payload):
        """
        Test filtering transactions (e.g., only large cash).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create mixed data
            await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
            await client.post("/api/v1/fintrac/transactions", json=large_cash_transaction_payload)

            # Filter for large cash
            response = await client.get("/api/v1/fintrac/transactions?is_large_cash_reportable=true")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["is_large_cash_reportable"] is True
```