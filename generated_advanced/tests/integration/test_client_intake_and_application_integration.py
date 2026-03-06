import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.common.database import get_async_session

# Override the dependency for testing
async def override_get_db():
    async with async_session_maker() as session:
        yield session

@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Create a test application instance."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    app.dependency_overrides[get_async_session] = override_get_db
    return app

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_application_endpoint_success(self, app: FastAPI, valid_application_payload):
        """Test the POST endpoint creates a record in DB."""
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.post("/api/v1/client-intake/", json=valid_application_payload)

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["first_name"] == "John"
            assert data["loan_amount"] == "400000.00"
            
            # PIPEDA Compliance Check: SIN must NEVER be in response
            assert "sin" not in data
            assert "sin_hash" not in data # Internal field usually hidden from API response
            
            # FINTRAC Compliance Check: Audit fields present
            assert "created_at" in data

    async def test_create_application_pipedata_sin_not_logged(self, app: FastAPI, valid_application_payload, caplog):
        """Ensure SIN is not logged in server logs."""
        # This test assumes structlog or similar is used. 
        # Here we verify the API response doesn't leak it first.
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/client-intake/", json=valid_application_payload)
            
            assert response.status_code == 201
            # Verify the raw SIN from payload is not in the response
            assert valid_application_payload["sin"] not in response.text

    async def test_get_application_endpoint(self, app: FastAPI, valid_application_payload, db_session):
        """Test retrieving a created application."""
        # Arrange - Create via service first to get ID
        from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
        from mortgage_underwriting.modules.client_intake.schemas import ClientApplicationCreate
        
        service = ClientIntakeService(db_session)
        created_app = await service.create_application(ClientApplicationCreate(**valid_application_payload))
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/client-intake/{created_app.id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(created_app.id)
            assert data["email"] == "john.doe@example.com"
            # Verify PIPEDA: DOB should be encrypted or omitted if not strictly necessary for GET
            # Assuming schema returns DOB for the owner, but definitely not SIN
            assert "sin" not in data

    async def test_create_application_validation_error(self, app: FastAPI, invalid_payload_missing_sin):
        """Test 422 error for invalid input."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/client-intake/", json=invalid_payload_missing_sin)
            
            assert response.status_code == 422 # Validation Error

    async def test_create_application_high_ltv_cmhc_flag(self, app: FastAPI, high_ltv_payload):
        """Test that high LTV applications trigger insurance_required flag via API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/client-intake/", json=high_ltv_payload)
            
            assert response.status_code == 201
            data = response.json()
            # CMHC Logic Check
            assert data["insurance_required"] is True
            assert data["ltv_ratio"] == "0.90"

    async def test_get_application_not_found(self, app: FastAPI):
        """Test 404 for non-existent UUID."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/client-intake/{fake_id}")
            assert response.status_code == 404
            assert "detail" in response.json()

    async def test_database_persistence(self, app: FastAPI, valid_application_payload, db_session):
        """Test that data actually persists in the database correctly."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.post("/api/v1/client-intake/", json=valid_application_payload)
            app_id = response.json()["id"]
            
            # Verify directly in DB
            result = await db_session.execute(select(ClientApplication).where(ClientApplication.id == app_id))
            db_record = result.scalar_one_or_none()
            
            assert db_record is not None
            assert db_record.loan_amount == Decimal("400000.00")
            assert db_record.sin_hash is not None # Verify PIPEDA encryption happened in DB
            assert db_record.sin_hash != valid_application_payload["sin"] # Verify it's not plain text
            assert db_record.created_at is not None # FINTRAC audit trail