import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport, ClientIdentity

@pytest.mark.integration
class TestFintracIntegration:

    @pytest.mark.asyncio
    async def test_create_and_retrieve_report(self, client: AsyncClient, db_session):
        """Test full workflow of creating a report and retrieving it."""
        # 1. Create Report
        payload = {
            "client_id": "int_client_01",
            "transaction_amount": "7500.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "entity_type": "individual"
        }
        response = await client.post("/api/v1/fintrac/reports", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["client_id"] == "int_client_01"
        assert data["is_large_cash_transaction"] is False
        
        # 2. Verify in DB
        stmt = select(FintracReport).where(FintracReport.client_id == "int_client_01")
        result = await db_session.execute(stmt)
        db_report = result.scalar_one_or_none()
        
        assert db_report is not None
        assert db_report.transaction_amount == Decimal("7500.00")
        assert db_report.created_at is not None

    @pytest.mark.asyncio
    async def test_large_cash_transaction_flagging(self, client: AsyncClient, db_session):
        """Test that large cash transactions (>10k) are flagged via API."""
        payload = {
            "client_id": "int_client_02",
            "transaction_amount": "12000.00",
            "currency": "CAD",
            "transaction_type": "cash_deposit",
            "entity_type": "individual"
        }
        
        response = await client.post("/api/v1/fintrac/reports", json=payload)
        assert response.status_code == 201
        data = response.json()
        
        assert data["is_large_cash_transaction"] is True
        
        # Check DB persistence
        stmt = select(FintracReport).where(FintracReport.client_id == "int_client_02")
        result = await db_session.execute(stmt)
        db_report = result.scalar_one_or_none()
        assert db_report.is_large_cash_transaction is True

    @pytest.mark.asyncio
    async def test_identity_verification_pii_protection(self, client: AsyncClient, db_session):
        """Test that identity verification does not return plain SIN."""
        payload = {
            "client_id": "int_client_03",
            "first_name": "Alice",
            "last_name": "Wonderland",
            "sin": "123-456-789",
            "dob": "1992-02-02",
            "occupation": "Designer"
        }
        
        response = await client.post("/api/v1/fintrac/verify-identity", json=payload)
        assert response.status_code == 201
        data = response.json()
        
        # CRITICAL: Ensure SIN is NOT in the response
        assert "sin" not in data
        assert "123-456-789" not in str(data)
        assert data["client_id"] == "int_client_03"
        
        # Verify DB storage (Hashed/Encrypted)
        stmt = select(ClientIdentity).where(ClientIdentity.client_id == "int_client_03")
        result = await db_session.execute(stmt)
        db_identity = result.scalar_one_or_none()
        
        assert db_identity is not None
        # Assuming model has sin_encrypted or sin_hash
        # Ensure plain SIN is not stored in a plain 'sin' column
        assert getattr(db_identity, 'sin', None) != "123-456-789"

    @pytest.mark.asyncio
    async def test_transaction_validation_error(self, client: AsyncClient):
        """Test API validation for invalid inputs."""
        # Negative amount
        payload = {
            "client_id": "int_client_04",
            "transaction_amount": "-50.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "entity_type": "individual"
        }
        
        response = await client.post("/api/v1/fintrac/reports", json=payload)
        assert response.status_code == 422 # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_get_fintrac_report_endpoint(self, client: AsyncClient, db_session):
        """Test retrieving a specific report by ID."""
        # Seed data
        new_report = FintracReport(
            client_id="int_client_05",
            transaction_amount=Decimal("2500.00"),
            currency="CAD",
            transaction_type="etransfer",
            entity_type="individual",
            is_large_cash_transaction=False
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)
        
        # Fetch via API
        response = await client.get(f"/api/v1/fintrac/reports/{new_report.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == new_report.id
        assert data["transaction_amount"] == "2500.00"

    @pytest.mark.asyncio
    async def test_fintrac_audit_trail_fields(self, client: AsyncClient, db_session):
        """Test that audit fields are automatically populated."""
        payload = {
            "client_id": "int_client_06",
            "transaction_amount": "100.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "entity_type": "individual"
        }
        
        await client.post("/api/v1/fintrac/reports", json=payload)
        
        stmt = select(FintracReport).where(FintracReport.client_id == "int_client_06")
        result = await db_session.execute(stmt)
        report = result.scalar_one_or_none()
        
        assert report.created_at is not None
        assert report.updated_at is not None
        # Assuming created_by is handled by middleware or service, if not, it might be null/system
        # But fields must exist.
        assert hasattr(report, 'created_at')
        assert hasattr(report, 'created_by')

    @pytest.mark.asyncio
    async def test_nonexistent_report_returns_404(self, client: AsyncClient):
        """Test getting a report that doesn't exist."""
        response = await client.get("/api/v1/fintrac/reports/99999")
        assert response.status_code == 404
        assert "detail" in response.json()