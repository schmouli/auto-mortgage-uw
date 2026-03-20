```python
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.fintrac.models import TransactionRecord, AuditLog

@pytest.mark.integration
class TestFintracIntegration:

    async def test_create_transaction_endpoint_201(self, client: AsyncClient, valid_transaction_payload):
        """Test full flow of creating a transaction via API."""
        response = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["client_id"] == "client-123"
        assert data["amount"] == "5000.00"
        assert data["is_large_cash_transaction"] is False
        assert "created_at" in data

    async def test_create_large_cash_transaction_flag_integration(self, client: AsyncClient, large_cash_transaction_payload):
        """Test API correctly flags > $10k transactions."""
        response = await client.post("/api/v1/fintrac/transactions", json=large_cash_transaction_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["is_large_cash_transaction"] is True
        assert data["transaction_type"] == "cash_deposit"

    async def test_create_transaction_persists_to_db(self, client: AsyncClient, db_session, valid_transaction_payload):
        """Verify data is actually written to PostgreSQL/SQLite."""
        response = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
        assert response.status_code == 201
        
        # Query DB directly
        result = await db_session.execute(select(TransactionRecord).where(TransactionRecord.client_id == "client-123"))
        record = result.scalar_one_or_none()
        
        assert record is not None
        assert record.amount == Decimal("5000.00")
        assert record.created_by is not None # Audit trail check

    async def test_create_transaction_validation_error_negative(self, client: AsyncClient):
        """Test API rejects invalid data (negative amount)."""
        payload = {
            "client_id": "client-999",
            "amount": "-100.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "account_number": "****0000"
        }
        response = await client.post("/api/v1/fintrac/transactions", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_create_transaction_validation_missing_field(self, client: AsyncClient):
        """Test API rejects missing required fields."""
        payload = {
            "client_id": "client-999",
            "amount": "100.00"
            # Missing currency, type, etc.
        }
        response = await client.post("/api/v1/fintrac/transactions", json=payload)
        
        assert response.status_code == 422

    async def test_verify_identity_endpoint_creates_audit_log(self, client: AsyncClient, db_session, valid_verification_payload):
        """Test identity verification creates an audit trail."""
        response = await client.post("/api/v1/fintrac/verify-identity", json=valid_verification_payload)
        
        assert response.status_code == 201
        
        # Check Audit Log
        result = await db_session.execute(select(AuditLog).where(AuditLog.client_id == "client-123"))
        log = result.scalar_one_or_none()
        
        assert log is not None
        assert log.action == "IDENTITY_VERIFICATION"
        assert log.details is not None

    async def test_get_transaction_retrieval(self, client: AsyncClient, db_session, valid_transaction_payload):
        """Test retrieving a specific transaction."""
        # Create first
        create_resp = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
        trans_id = create_resp.json()["id"]
        
        # Retrieve
        get_resp = await client.get(f"/api/v1/fintrac/transactions/{trans_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == trans_id

    async def test_transaction_immutability_attempt(self, client: AsyncClient, db_session, valid_transaction_payload):
        """
        Test that updating audit fields (created_at) is rejected by the system.
        Note: Depending on API implementation, PUT might not exist or might ignore these fields.
        Here we test that the service doesn't allow changing created_at via an update endpoint if it exists.
        """
        create_resp = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
        trans_id = create_resp.json()["id"]
        original_created_at = create_resp.json()["created_at"]
        
        # Attempt update (assuming endpoint exists for modifying status, not audit fields)
        update_payload = {
            "status": "reviewed",
            "created_at": "2020-01-01T00:00:00" # Malicious attempt to change audit trail
        }
        
        # If the API has an update endpoint
        update_resp = await client.patch(f"/api/v1/fintrac/transactions/{trans_id}", json=update_payload)
        
        if update_resp.status_code == 200:
            # Verify created_at did not change
            get_resp = await client.get(f"/api/v1/fintrac/transactions/{trans_id}")
            assert get_resp.json()["created_at"] == original_created_at
        elif update_resp.status_code == 400:
            # API correctly rejected the attempt
            pass

    async def test_list_transactions_filter_by_client(self, client: AsyncClient, db_session):
        """Test filtering transactions for a specific client."""
        # Create two transactions for different clients
        payload1 = {"client_id": "client-A", "amount": "100.00", "currency": "CAD", "transaction_type": "wire", "account_number": "****1"}
        payload2 = {"client_id": "client-B", "amount": "200.00", "currency": "CAD", "transaction_type": "wire", "account_number": "****2"}
        
        await client.post("/api/v1/fintrac/transactions", json=payload1)
        await client.post("/api/v1/fintrac/transactions", json=payload2)
        
        # List for client-A
        response = await client.get("/api/v1/fintrac/transactions?client_id=client-A")
        
        assert response.status_code == 200
        data = response.json()
        # Assuming pagination or list response
        items = data.get("items", data) if isinstance(data, dict) else data
        
        assert len(items) == 1
        assert items[0]["client_id"] == "client-A"

    async def test_financial_data_types_response(self, client: AsyncClient, valid_transaction_payload):
        """Ensure API returns financial data as strings (to preserve precision) or correct format."""
        response = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
        assert response.status_code == 201
        
        data = response.json()
        # Check that amount is a string representation of the decimal
        assert isinstance(data["amount"], str)
        # Verify no float rounding issues
        assert Decimal(data["amount"]) == Decimal("5000.00")
```