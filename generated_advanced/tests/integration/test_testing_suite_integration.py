```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.testing_suite.models import UnderwritingTest

@pytest.mark.integration
class TestUnderwritingTestRoutes:

    @pytest.mark.asyncio
    async def test_create_test_scenario_success(self, client: AsyncClient, valid_test_payload):
        # Act
        response = await client.post("/api/v1/testing-suite", json=valid_test_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == valid_test_payload["name"]
        assert data["contract_rate"] == valid_test_payload["contract_rate"]
        # Verify Decimal is serialized correctly (string)
        assert data["principal_amount"] == valid_test_payload["principal_amount"]
        
        # Verify audit fields are present
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_test_scenario_invalid_input(self, client: AsyncClient, invalid_test_payload):
        # Act
        response = await client.post("/api/v1/testing-suite", json=invalid_test_payload)

        # Assert
        assert response.status_code == 422  # Validation Error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_test_scenario_success(self, client: AsyncClient, db_session, valid_test_payload):
        # Arrange - Create directly in DB
        new_test = UnderwritingTest(**valid_test_payload)
        db_session.add(new_test)
        await db_session.commit()
        await db_session.refresh(new_test)
        test_id = new_test.id

        # Act
        response = await client.get(f"/api/v1/testing-suite/{test_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_id
        assert data["name"] == valid_test_payload["name"]

    @pytest.mark.asyncio
    async def test_get_test_scenario_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/testing-suite/99999")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error_code" in data

    @pytest.mark.asyncio
    async def test_create_and_retrieve_workflow(self, client: AsyncClient, valid_test_payload):
        # 1. Create
        create_resp = await client.post("/api/v1/testing-suite", json=valid_test_payload)
        assert create_resp.status_code == 201
        test_id = create_resp.json()["id"]

        # 2. Retrieve
        get_resp = await client.get(f"/api/v1/testing-suite/{test_id}")
        assert get_resp.status_code == 200
        
        # 3. Verify Data Integrity
        retrieved_data = get_resp.json()
        assert Decimal(retrieved_data["contract_rate"]) == Decimal(valid_test_payload["contract_rate"])
        assert Decimal(retrieved_data["annual_income"]) == Decimal(valid_test_payload["annual_income"])

    @pytest.mark.asyncio
    async def test_financial_data_precision(self, client: AsyncClient, db_session):
        # Arrange - Payload with many decimal places to test rounding/truncation handling
        precise_payload = {
            "name": "Precision Test",
            "description": "Testing decimal precision",
            "contract_rate": "4.125",
            "principal_amount": "1000000.555", # Should be handled by DB/Pydantic constraints
            "amortization_years": 30,
            "annual_income": "150000.00",
            "property_tax": "3600.00",
            "heating": "1200.00",
            "other_debt": "0.00"
        }

        # Act
        response = await client.post("/api/v1/testing-suite", json=precise_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        # Ensure we are returning strings for Decimal to avoid float precision loss in JSON
        assert isinstance(data["principal_amount"], str)
        # Depending on model configuration (e.g. Decimal(10,2)), this might be rounded
        # Here we just check it's a valid Decimal string representation
        Decimal(data["principal_amount"])

    @pytest.mark.asyncio
    async def test_osfi_compliance_fields_present(self, client: AsyncClient, valid_test_payload):
        # Ensure that fields required for OSFI calculations are accepted and stored
        response = await client.post("/api/v1/testing-suite", json=valid_test_payload)
        assert response.status_code == 201
        
        data = response.json()
        # Check fields required for GDS/TDS
        assert "principal_amount" in data
        assert "annual_income" in data
        assert "property_tax" in data
        assert "heating" in data
        assert "other_debt" in data
        assert "amortization_years" in data

    @pytest.mark.asyncio
    async def test_data_minimization_no_extra_fields(self, client: AsyncClient, valid_test_payload):
        # PIPEDA: Data minimization. If we send extra fields not in schema, they should be ignored or rejected
        # FastAPI by default ignores extra fields if model config is set, or validates if not.
        # Assuming strict validation:
        extra_payload = valid_test_payload.copy()
        extra_payload["unnecessary_sensitive_info"] = "Some Data"

        response = await client.post("/api/v1/testing-suite", json=extra_payload)
        
        # If schema is strict, this might 422. If it ignores, it 201s but doesn't store.
        # Assuming Pydantic v2 default (ignore extra or error based on config).
        # We will assume it creates successfully but ignores the extra data.
        assert response.status_code in [201, 422]
        
        if response.status_code == 201:
            data = response.json()
            assert "unnecessary_sensitive_info" not in data
```