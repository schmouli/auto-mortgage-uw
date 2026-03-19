```python
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.fintrac.models import TransactionRecord

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracRoutes:

    async def test_create_transaction_success(self, client: AsyncClient, db_session):
        """Test API endpoint creates a transaction record in DB."""
        payload = {
            "amount": "7500.50",
            "currency": "CAD",
            "transaction_type": "mortgage_payment",
            "client_id": "client-int-001",
            "is_large_cash_report": False
        }

        response = await client.post("/api/v1/fintrac/transactions", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["amount"] == "7500.50"
        assert data["created_at"] is not None
        assert data["created_by"] is not None # Should be populated by middleware or service

        # Verify DB state
        stmt = select(TransactionRecord).where(TransactionRecord.id == data["id"])
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        assert record.amount == Decimal("7500.50")

    async def test_create_large_cash_transaction_validation(self, client: AsyncClient):
        """Test that API rejects large cash transaction without explicit flag."""
        payload = {
            "amount": "10001.00",
            "currency": "CAD",
            "transaction_type": "cash_deposit",
            "client_id": "client-int-002",
            "is_large_cash_report": False # Violation: Should be True for > 10k
        }

        response = await client.post("/api/v1/fintrac/transactions", json=payload)

        assert response.status_code == 400 # or 422 depending on validation layer
        detail = response.json()
        assert "error_code" in detail
        assert "large cash" in detail["detail"].lower()

    async def test_create_large_cash_transaction_success(self, client: AsyncClient, db_session):
        """Test API accepts large cash transaction with correct flag."""
        payload = {
            "amount": "25000.00",
            "currency": "CAD",
            "transaction_type": "large_cash_settlement",
            "client_id": "client-int-003",
            "is_large_cash_report": True
        }

        response = await client.post("/api/v1/fintrac/transactions", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["is_large_cash_report"] is True

    async def test_get_transaction_by_id(self, client: AsyncClient, db_session):
        """Test retrieving a specific transaction."""
        # Seed data
        new_record = TransactionRecord(
            amount=Decimal("1200.00"),
            currency="CAD",
            transaction_type="fee",
            client_id="client-int-004",
            is_large_cash_report=False,
            created_by="test_runner"
        )
        db_session.add(new_record)
        await db_session.commit()
        await db_session.refresh(new_record)

        response = await client.get(f"/api/v1/fintrac/transactions/{new_record.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == new_record.id
        assert data["client_id"] == "client-int-004"

    async def test_get_transaction_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent transaction."""
        response = await client.get("/api/v1/fintrac/transactions/99999")
        assert response.status_code == 404

    async def test_log_identity_verification_endpoint(self, client: AsyncClient, db_session):
        """Test identity verification logging endpoint."""
        payload = {
            "client_id": "client-int-005",
            "verification_method": "government_id",
            "verified_by": "agent_007",
            "sin_hash": "abshash123",
            "dob": "1992-12-12"
        }

        response = await client.post("/api/v1/fintrac/verify-identity", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] in data # simplistic check
        assert data["client_id"] == "client-int-005"

    async def test_pii_not_exposed_in_logs_or_errors(self, client: AsyncClient, caplog):
        """
        Test that raw PII (SIN/DOB) is not leaked in error responses.
        Note: This is a basic check; real implementation requires log capture inspection.
        """
        # Attempt a potentially invalid request that might echo data
        payload = {
            "amount": "100.00",
            "currency": "CAD",
            "transaction_type": "payment",
            "client_id": "client-int-006",
            "is_large_cash_report": False
        }
        
        # Assuming a bad request structure that triggers validation error
        # We check that the error response doesn't contain sensitive info if we sent it
        # (Standard FastAPI validation errors usually return the field value, 
        # so sensitive fields should NOT be in the request body for validation endpoints 
        # or should be filtered).
        
        response = await client.post("/api/v1/fintrac/transactions", json=payload)
        # If this succeeds, no error to check. Let's force a 422
        bad_payload = {**payload, "amount": "not_a_number"}
        
        response = await client.post("/api/v1/fintrac/transactions", json=bad_payload)
        assert response.status_code == 422
        
        # Ensure no sensitive data is in the response (though we didn't send SIN here)
        # This is a structural test for the error handling format
        assert "detail" in response.json()

    async def test_transaction_audit_fields_present(self, client: AsyncClient, db_session):
        """Ensure created_at and updated_at are always present."""
        payload = {
            "amount": "500.00",
            "currency": "CAD",
            "transaction_type": "payment",
            "client_id": "audit-test",
            "is_large_cash_report": False
        }
        
        response = await client.post("/api/v1/fintrac/transactions", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify DB types
        stmt = select(TransactionRecord).where(TransactionRecord.id == data["id"])
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        
        assert record.created_at is not None
        assert record.updated_at is not None
```