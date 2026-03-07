```python
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_portal.models import MortgageApplication
from mortgage_underwriting.modules.client_portal.routes import router
from mortgage_underwriting.common.database import get_async_session


# Override the dependency for testing
async def override_get_db():
    from mortgage_underwriting.tests.conftest import TestingSessionLocal
    async with TestingSessionLocal() as session:
        yield session


@pytest.mark.integration
class TestClientPortalEndpoints:
    """
    Integration tests for Client Portal API endpoints.
    Tests the full HTTP request/response cycle and DB state.
    """

    @pytest.mark.asyncio
    async def test_create_application_success(self, app, client, valid_application_payload):
        """
        Test creating a new application via POST.
        """
        # Override DB dependency
        app.dependency_overrides[get_async_session] = override_get_db
        
        response = await client.post("/api/v1/client-portal/applications", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["status"] == "submitted"
        assert data["first_name"] == "John"
        
        # Verify PII is NOT in response (PIPEDA)
        assert "sin" not in data
        assert "date_of_birth" not in data
        
        # Verify Financials are Decimal strings
        assert data["loan_amount"] == "400000.00"
        
        # Cleanup
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_create_application_validation_error(self, app, client):
        """
        Test 422 Unprocessable Entity on invalid schema.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        invalid_payload = {
            "first_name": "", # Empty string
            "loan_amount": "not_a_number"
        }
        
        response = await client.post("/api/v1/client-portal/applications", json=invalid_payload)
        
        assert response.status_code == 422
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_create_application_gds_rejection(self, app, client, valid_application_payload):
        """
        Test that business logic validation (GDS) returns 400 Bad Request.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        payload = valid_application_payload.copy()
        payload["annual_income"] = Decimal("30000.00") # Very low income
        
        response = await client.post("/api/v1/client-portal/applications", json=payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "GDS" in data["detail"]
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, app, client):
        """
        Test GET /applications/{id} with non-existent ID.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        response = await client.get("/api/v1/client-portal/applications/99999")
        
        assert response.status_code == 404
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_application_success(self, app, client, db_session, valid_application_payload):
        """
        Test retrieving an existing application.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        # 1. Create an application directly in DB
        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        created_app = await service.submit_application(ApplicationCreate(**valid_application_payload))
        await db_session.commit()
        
        # 2. Retrieve via API
        response = await client.get(f"/api/v1/client-portal/applications/{created_app.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_app.id
        assert data["email"] == "john.doe@example.com"
        
        # Ensure PII is filtered out
        assert "sin" not in data
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_applications_empty(self, app, client):
        """
        Test GET /applications returns empty list initially.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        response = await client.get("/api/v1/client-portal/applications")
        
        assert response.status_code == 200
        assert response.json() == []
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_update_application_status(self, app, client, db_session, valid_application_payload):
        """
        Test PATCH /applications/{id}/status (Internal/Underwriting view, but exposed via portal for status checks).
        Assuming client can only view, but let's test a hypothetical update endpoint or verify read-only nature.
        Here we test a GET request specifically for status.
        """
        app.dependency_overrides[get_async_session] = override_get_db

        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        created_app = await service.submit_application(ApplicationCreate(**valid_application_payload))
        await db_session.commit()

        # Update status manually in DB to simulate underwriting
        created_app.status = "approved"
        await db_session.commit()
        await db_session.refresh(created_app)

        response = await client.get(f"/api/v1/client-portal/applications/{created_app.id}")
        
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_audit_fields_persistence(self, app, client, db_session, valid_application_payload):
        """
        Test FINTRAC requirement: Audit trail (created_at, updated_at).
        """
        app.dependency_overrides[get_async_session] = override_get_db

        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        app_obj = await service.submit_application(ApplicationCreate(**valid_application_payload))
        await db_session.commit()
        await db_session.refresh(app_obj)
        
        assert app_obj.created_at is not None
        assert app_obj.updated_at is not None
        
        # Verify it's not the default epoch
        assert app_obj.created_at.year > 2000

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_cmhc_insurance_flag_in_response(self, app, client, db_session):
        """
        Test that CMHC insurance calculation is reflected in the GET response.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        payload = {
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "1990-01-01",
            "sin": "111222333",
            "email": "test@example.com",
            "phone_number": "4165550199",
            "property_address": "789 Pine St",
            "property_value": "400000.00",
            "down_payment": "20000.00", # 5% down -> 95% LTV
            "loan_amount": "380000.00",
            "contract_rate": "5.0",
            "amortization_years": 25,
            "annual_income": "100000.00",
            "property_tax": "3000.00",
            "heating_cost": "1200.00",
            "other_debt": "0.00",
        }

        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        app_obj = await service.submit_application(ApplicationCreate(**payload))
        await db_session.commit()
        
        response = await client.get(f"/api/v1/client-portal/applications/{app_obj.id}")
        data = response.json()
        
        assert data["insurance_required"] is True
        # 95% LTV -> 4.00% premium. 380000 * 0.04 = 15200
        assert Decimal(data["insurance_premium"]) == Decimal("15200.00")
        
        app.dependency_overrides = {}
```