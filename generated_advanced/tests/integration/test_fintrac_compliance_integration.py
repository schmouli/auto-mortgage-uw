import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal
from datetime import datetime

from mortgage_underwriting.modules.fintrac.routes import router
from mortgage_underwriting.modules.fintrac.models import FintracReport, IdentityVerificationLog
from mortgage_underwriting.common.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

# Override the dependency for testing
async def override_get_db():
    # This would use the fixture from conftest in a real run
    # For integration tests, we usually bind the engine to the tables
    pass

@pytest.fixture
def app(engine):
    """Create a test FastAPI app with the Fintrac router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/fintrac")
    
    # Setup tables
    from mortgage_underwriting.modules.fintrac.models import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker
    
    @app.on_event("startup")
    async def startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    return app

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracIntegration:

    async def test_create_identity_verification_log(self, app: FastAPI, db_session: AsyncSession):
        """
        Test POST /verify-identity
        Ensures the record is created in the DB and response is 201.
        """
        # Override dependency
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "applicant_id": "applicant-001",
                "verification_method": "passport",
                "verified_by": "agent_007"
            }
            
            response = await client.post("/api/v1/fintrac/verify-identity", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] is not None
            assert data["applicant_id"] == "applicant-001"
            assert data["verification_method"] == "passport"
            
            # Verify DB State
            result = await db_session.execute(
                select(IdentityVerificationLog).where(IdentityVerificationLog.applicant_id == "applicant-001")
            )
            log = result.scalar_one_or_none()
            assert log is not None
            assert log.verified_by == "agent_007"
            
        app.dependency_overrides.clear()

    async def test_create_transaction_large_cash_flagging(self, app: FastAPI, db_session: AsyncSession):
        """
        Test POST /transactions
        Ensures amounts >= 10k are flagged in DB and response.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "applicant_id": "applicant-002",
                "transaction_amount": "15000.00",
                "transaction_type": "wire_transfer",
                "currency": "CAD"
            }
            
            response = await client.post("/api/v1/fintrac/transactions", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["is_large_cash"] is True
            
            # Verify DB State
            result = await db_session.execute(
                select(FintracReport).where(FintracReport.applicant_id == "applicant-002")
            )
            report = result.scalar_one_or_none()
            assert report is not None
            assert report.transaction_amount == Decimal("15000.00")
            assert report.is_large_cash is True

        app.dependency_overrides.clear()

    async def test_create_transaction_small_cash(self, app: FastAPI, db_session: AsyncSession):
        """
        Test POST /transactions
        Ensures amounts < 10k are not flagged.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "applicant_id": "applicant-003",
                "transaction_amount": "9999.99",
                "transaction_type": "deposit",
                "currency": "CAD"
            }
            
            response = await client.post("/api/v1/fintrac/transactions", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["is_large_cash"] is False

        app.dependency_overrides.clear()

    async def test_get_fintrac_reports(self, app: FastAPI, db_session: AsyncSession):
        """
        Test GET /reports
        Verifies retrieval of logged reports.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        # Seed data
        new_report = FintracReport(
            applicant_id="applicant-004",
            transaction_amount=Decimal("500.00"),
            transaction_type="fee",
            currency="CAD",
            is_large_cash=False
        )
        db_session.add(new_report)
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/fintrac/reports")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
            assert any(r["applicant_id"] == "applicant-004" for r in data)

        app.dependency_overrides.clear()

    async def test_update_prevention_on_audit_fields(self, app: FastAPI, db_session: AsyncSession):
        """
        Test PATCH /reports/{id}
        Attempts to update created_at should fail.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        # Seed data
        new_report = FintracReport(
            applicant_id="applicant-005",
            transaction_amount=Decimal("100.00"),
            transaction_type="fee",
            currency="CAD",
            is_large_cash=False
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Attempt to update created_at
            update_payload = {
                "created_at": "2024-01-01T00:00:00Z"
            }
            
            response = await client.patch(f"/api/v1/fintrac/reports/{new_report.id}", json=update_payload)
            
            assert response.status_code == 400 # Bad Request / Validation Error
            assert "immutable" in response.json()["detail"].lower()

        app.dependency_overrides.clear()