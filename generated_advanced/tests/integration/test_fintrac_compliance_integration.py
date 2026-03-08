import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracRoutes:

    async def test_create_report_endpoint_success(self, client: AsyncClient, valid_report_payload):
        """Test creating a report via API and verifying DB state."""
        response = await client.post("/api/v1/fintrac/reports", json=valid_report_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["amount"] == "5000.00"
        assert data["is_high_value"] is False
        assert "created_at" in data

    async def test_create_high_value_report_flag(self, client: AsyncClient, high_value_report_payload):
        """Test that high value transactions are flagged automatically by the API."""
        response = await client.post("/api/v1/fintrac/reports", json=high_value_report_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["is_high_value"] is True
        assert data["amount"] == "12500.00"

    async def test_create_report_invalid_amount(self, client: AsyncClient, invalid_report_payload):
        """Test API rejection of invalid (negative) amounts."""
        response = await client.post("/api/v1/fintrac/reports", json=invalid_report_payload)
        
        assert response.status_code == 422 # Validation error

    async def test_get_report_endpoint(self, client: AsyncClient, valid_report_payload, db_session):
        """Test retrieving a created report."""
        # Create a report first
        create_resp = await client.post("/api/v1/fintrac/reports", json=valid_report_payload)
        report_id = create_resp.json()["id"]

        # Retrieve it
        get_resp = await client.get(f"/api/v1/fintrac/reports/{report_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == report_id
        assert data["transaction_type"] == "eft"

    async def test_get_report_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent report."""
        response = await client.get("/api/v1/fintrac/reports/99999")
        assert response.status_code == 404

    async def test_list_reports_pagination(self, client: AsyncClient, valid_report_payload):
        """Test listing reports with pagination."""
        # Create 3 reports
        for _ in range(3):
            await client.post("/api/v1/fintrac/reports", json=valid_report_payload)

        response = await client.get("/api/v1/fintrac/reports?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1

    async def test_audit_trail_immutability(self, client: AsyncClient, valid_report_payload, db_session):
        """
        Test that created_at and created_by are populated and cannot be updated via standard update endpoint 
        (or that update logic preserves them).
        """
        # Create
        create_resp = await client.post("/api/v1/fintrac/reports", json=valid_report_payload)
        report_id = create_resp.json()["id"]
        original_created_at = create_resp.json()["created_at"]
        
        # Verify DB state
        stmt = select(FintracReport).where(FintracReport.id == report_id)
        result = await db_session.execute(stmt)
        db_obj = result.scalar_one_or_none()
        
        assert db_obj is not None
        assert db_obj.created_by == "system_user"
        assert db_obj.created_at is not None

        # Attempt Update (if endpoint exists)
        # Assuming a PUT/PATCH endpoint exists for amount/status but NOT audit fields
        update_payload = {"amount": "6000.00"}
        update_resp = await client.patch(f"/api/v1/fintrac/reports/{report_id}", json=update_payload)
        
        if update_resp.status_code == 200:
            # Fetch again to ensure audit fields didn't change
            await db_session.refresh(db_obj)
            assert db_obj.amount == Decimal("6000.00")
            assert db_obj.created_by == "system_user" # Should remain unchanged
            assert str(db_obj.created_at) == original_created_at

    async def test_financial_precision_integrity(self, client: AsyncClient, db_session):
        """Test that decimal precision is maintained through the API and DB."""
        precise_payload = {
            "amount": "12345.6789", # High precision
            "transaction_type": "wire",
            "created_by": "precision_test"
        }
        
        response = await client.post("/api/v1/fintrac/reports", json=precise_payload)
        assert response.status_code == 201
        
        report_id = response.json()["id"]
        stmt = select(FintracReport).where(FintracReport.id == report_id)
        result = await db_session.execute(stmt)
        db_obj = result.scalar_one_or_none()
        
        # Verify strict Decimal equality
        assert db_obj.amount == Decimal("12345.6789")