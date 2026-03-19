import pytest
from httpx import AsyncClient, ASGITransport
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision
from mortgage_underwriting.modules.underwriting_engine.schemas import DecisionStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestUnderwritingEndpoints:

    async def test_create_underwriting_decision_success(self, app, valid_underwriting_request, db_session):
        """
        Test full workflow: API Request -> Processing -> DB Persistence -> Response
        """
        # Override dependency to use test session
        app.dependency_overrides[get_async_session] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/assess", json=valid_underwriting_request)

        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["status"] == "APPROVED"
        assert "gds" in data
        assert "tds" in data
        assert "ltv" in data
        assert "created_at" in data # FINTRAC: Audit trail
        assert "sin_hash" not in data # PIPEDA: Minimization in response

        # Verify DB Record
        stmt = select(UnderwritingDecision).where(UnderwritingDecision.id == data["id"])
        result = await db_session.execute(stmt)
        db_record = result.scalar_one()

        assert db_record is not None
        assert db_record.status == DecisionStatus.APPROVED
        assert db_record.loan_amount == Decimal("400000.00")
        assert db_record.created_at is not None

        app.dependency_overrides.clear()

    async def test_create_underwriting_decision_rejection_high_tds(self, app, db_session):
        """
        Test API response for a rejected application (High TDS).
        """
        payload = {
            "applicant": {
                "first_name": "Test",
                "last_name": "User",
                "sin_hash": "hash123",
                "date_of_birth": "1990-01-01"
            },
            "property": {
                "address": "123 St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M1M1M1",
                "value": "500000.00",
                "annual_property_tax": "3000.00",
                "estimated_heating_cost": "150.00"
            },
            "financial": {
                "annual_income": "60000.00", # Low income relative to debt
                "down_payment": "100000.00",
                "loan_amount": "400000.00",
                "amortization_years": 25,
                "contract_rate": "5.00",
                "other_debt_payments": "1500.00" # High debt
            }
        }

        app.dependency_overrides[get_async_session] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/assess", json=payload)

        # Even if rejected, we usually save the record (200 or 201), 
        # or return 422 if input validation fails. Assuming 201 with decision content.
        assert response.status_code == 201
        
        data = response.json()
        assert data["status"] == "REJECTED"
        assert "TDS" in data["rejection_reasons"]

        app.dependency_overrides.clear()

    async def test_get_underwriting_decision_by_id(self, app, valid_underwriting_request, db_session):
        """
        Test retrieving a specific decision record.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session

        # 1. Create a decision
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/underwriting/assess", json=valid_underwriting_request)
            decision_id = create_resp.json()["id"]

            # 2. Retrieve it
            get_resp = await client.get(f"/api/v1/underwriting/{decision_id}")

        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == decision_id
        assert data["status"] == "APPROVED"
        
        # Ensure immutable audit trail fields are present
        assert "created_at" in data

        app.dependency_overrides.clear()

    async def test_invalid_input_validation_missing_field(self, app, db_session):
        """
        Test that validation works for missing required fields.
        """
        invalid_payload = {
            "applicant": {
                "first_name": "Incomplete"
                # Missing last_name, sin_hash, dob
            },
            "property": {},
            "financial": {}
        }

        app.dependency_overrides[get_async_session] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/assess", json=invalid_payload)

        assert response.status_code == 422 # Unprocessable Entity
        errors = response.json()
        assert "detail" in errors

        app.dependency_overrides.clear()

    async def test_financial_data_precision_integrity(self, app, db_session):
        """
        Ensure that Decimal values are handled with full precision in the DB and API.
        """
        # Using specific cents to verify precision loss doesn't occur
        precise_payload = {
            "applicant": {
                "first_name": "Penny",
                "last_name": "Pincher",
                "sin_hash": "hash_precise",
                "date_of_birth": "1988-12-12"
            },
            "property": {
                "address": "555 Decimal Dr",
                "city": "Markham",
                "province": "ON",
                "postal_code": "L3R1A1",
                "value": "555555.55",
                "annual_property_tax": "3333.33",
                "estimated_heating_cost": "111.11"
            },
            "financial": {
                "annual_income": "88888.88",
                "down_payment": "11111.11",
                "loan_amount": "444444.44",
                "amortization_years": 30,
                "contract_rate": "3.33",
                "other_debt_payments": "222.22"
            }
        }

        app.dependency_overrides[get_async_session] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/assess", json=precise_payload)

        assert response.status_code == 201
        data = response.json()
        
        # Verify the values returned match the input precision
        assert Decimal(data["property_value"]) == Decimal("555555.55")
        assert Decimal(data["loan_amount"]) == Decimal("444444.44")
        
        # Check DB persistence
        stmt = select(UnderwritingDecision).where(UnderwritingDecision.id == data["id"])
        result = await db_session.execute(stmt)
        db_record = result.scalar_one()
        
        assert db_record.property_value == Decimal("555555.55")
        assert db_record.annual_income == Decimal("88888.88")

        app.dependency_overrides.clear()