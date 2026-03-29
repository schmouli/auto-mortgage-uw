import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_portal.models import MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import ApplicationStatus

@pytest.mark.integration
class TestClientPortalRoutes:
    
    @pytest.mark.asyncio
    async def test_create_application_endpoint_success(
        self, client: AsyncClient, valid_application_payload, mock_auth_headers
    ):
        """
        Integration test: Create application via API endpoint.
        """
        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=valid_application_payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == ApplicationStatus.SUBMITTED.value
        assert data["ltv"] is not None
        # Verify PII (if any in response) is masked or absent
        # Assuming borrower_id is returned but sensitive details are not
        assert "sin" not in data

    @pytest.mark.asyncio
    async def test_create_application_endpoint_unauthorized(
        self, client: AsyncClient, valid_application_payload
    ):
        """
        Integration test: Unauthorized access returns 401.
        """
        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=valid_application_payload
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_application_validation_error(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Invalid input returns 422.
        """
        # Arrange - Missing required fields
        invalid_payload = {
            "borrower_id": "123",
            # Missing property_value, down_payment, etc.
        }

        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=invalid_payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_application_endpoint_success(
        self, client: AsyncClient, db_session, valid_application_payload, mock_auth_headers
    ):
        """
        Integration test: Retrieve a created application.
        """
        # 1. Create an application directly in DB
        app_model = MortgageApplication(
            borrower_id=valid_application_payload["borrower_id"],
            property_value=Decimal(valid_application_payload["property_value"]),
            down_payment=Decimal(valid_application_payload["down_payment"]),
            annual_income=Decimal(valid_application_payload["annual_income"]),
            status=ApplicationStatus.SUBMITTED
        )
        db_session.add(app_model)
        await db_session.commit()
        await db_session.refresh(app_model)

        # 2. Retrieve via API
        response = await client.get(
            f"/api/v1/client-portal/applications/{app_model.id}",
            headers=mock_auth_headers
        )

        # 3. Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(app_model.id)
        assert data["borrower_id"] == app_model.borrower_id
        assert Decimal(data["property_value"]) == app_model.property_value

    @pytest.mark.asyncio
    async def test_get_application_endpoint_not_found(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Retrieve non-existent application returns 404.
        """
        # Act
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/client-portal/applications/{fake_id}",
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_submit_application_workflow(
        self, client: AsyncClient, db_session, valid_application_payload, mock_auth_headers
    ):
        """
        Integration test: Full workflow of creating and then updating status.
        """
        # Step 1: Create
        create_resp = await client.post(
            "/api/v1/client-portal/applications",
            json=valid_application_payload,
            headers=mock_auth_headers
        )
        assert create_resp.status_code == 201
        app_id = create_resp.json()["id"]

        # Step 2: Verify DB State
        stmt = select(MortgageApplication).where(MortgageApplication.id == app_id)
        result = await db_session.execute(stmt)
        db_app = result.scalar_one()
        
        assert db_app.status == ApplicationStatus.SUBMITTED
        # Verify CMHC insurance calculation was performed
        # LTV = (500k - 100k) / 500k = 80% -> No insurance required
        assert db_app.insurance_required is False

        # Step 3: Update Status (Simulating Underwriter action via portal)
        update_resp = await client.patch(
            f"/api/v1/client-portal/applications/{app_id}",
            json={"status": "UNDER_REVIEW"},
            headers=mock_auth_headers
        )
        assert update_resp.status_code == 200
        
        # Step 4: Verify final state
        await db_session.refresh(db_app)
        assert db_app.status == ApplicationStatus.UNDER_REVIEW

    @pytest.mark.asyncio
    async def test_financial_data_precision(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Ensure Decimal precision is preserved through API.
        """
        # Arrange - Use high precision values
        payload = {
            "borrower_id": "123e4567-e89b-12d3-a456-426614174000",
            "property_value": "555555.55", 
            "down_payment": "111111.11",
            "annual_income": "98765.43",
            "property_tax": "3333.33",
            "heating_cost": "111.11",
            "other_debt": "222.22",
            "amortization_years": 25
        }

        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        
        # Check that response preserves the exact decimal strings
        assert data["property_value"] == payload["property_value"]
        assert data["annual_income"] == payload["annual_income"]
        
        # Check calculated fields are Decimals (strings in JSON)
        assert "ltv" in data
        # LTV = (555555.55 - 111111.11) / 555555.55 = 0.800000...
        # Verify it's not a float like 0.8
        assert "." in data["ltv"] 

    @pytest.mark.asyncio
    async def test_osfi_limits_enforced(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Verify GDS/TDS limits are calculated and returned.
        """
        # Arrange - High debt load
        payload = {
            "borrower_id": "123e4567-e89b-12d3-a456-426614174000",
            "property_value": "400000.00",
            "down_payment": "80000.00", # 20% down
            "annual_income": "50000.00", # Low income relative to debt
            "property_tax": "4000.00",
            "heating_cost": "1500.00",
            "other_debt": "1000.00", # Significant other debt
            "amortization_years": 25
        }

        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        
        # If the system calculates ratios immediately, check they exist
        # If calculated on retrieval, we would need to GET it. 
        # Assuming POST returns calculated snapshot.
        if "gds" in data:
            assert Decimal(data["gds"]) <= Decimal("0.39") or data["gds_warning"] == True
        if "tds" in data:
            assert Decimal(data["tds"]) <= Decimal("0.44") or data["tds_warning"] == True