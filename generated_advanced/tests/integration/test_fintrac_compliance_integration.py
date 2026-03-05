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