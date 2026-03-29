```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from mortgage_underwriting.modules.borrower.models import Borrower
from mortgage_underwriting.modules.property.models import Property as PropertyModel
from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision

@pytest.mark.integration
@pytest.mark.asyncio
class TestUnderwritingEngineIntegration:
    """
    Integration tests for the Underwriting Engine API.
    Tests the full request lifecycle: API -> Service -> DB.
    """

    async def test_full_workflow_approve(self, app: "FastAPI", db_session: AsyncSession):
        """
        Test creating borrower, property, and then evaluating the mortgage.
        Expect APPROVED decision.
        """
        # 1. Setup Data in DB (Direct DB manipulation for setup)
        borrower = Borrower(
            first_name="Jane",
            last_name="Smith",
            sin_hash="hash123", # PII encrypted/hashed in real app
            date_of_birth="1990-01-01",
            credit_score=780,
            annual_income=Decimal("150000.00"),
            monthly_debt=Decimal("400.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="456 Oak Ave",
            city="Vancouver",
            province="BC",
            postal_code="V6A1B2",
            property_value=Decimal("1000000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        
        await db_session.commit()

        # 2. Call Underwriting API
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "800000.00", # 80% LTV
                    "down_payment": "200000.00",
                    "amortization_years": 25,
                    "contract_rate": "4.5",
                    "property_tax_annual": "6000.00",
                    "heating_cost_monthly": "200.00",
                    "condo_fees_monthly": "0.00"
                }
            )

        # 3. Assertions
        assert response.status_code == 201
        data = response.json()
        
        assert data["decision"] == "APPROVED"
        assert data["borrower_id"] == borrower.id
        assert data["insurance_required"] is False # LTV is 80%
        
        # Verify DB Record
        decision_record = await db_session.get(UnderwritingDecision, data["id"])
        assert decision_record is not None
        assert decision_record.decision == "APPROVED"

    async def test_full_workflow_reject_high_gds(self, app: "FastAPI", db_session: AsyncSession):
        """
        Test workflow where borrower is rejected due to high GDS.
        """
        # 1. Setup Data: High Property Tax/Low Income scenario
        borrower = Borrower(
            first_name="Low",
            last_name="Income",
            sin_hash="hash456",
            date_of_birth="1985-05-05",
            credit_score=700,
            annual_income=Decimal("60000.00"), # Low income
            monthly_debt=Decimal("0.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="789 Pine Rd",
            city="Toronto",
            province="ON",
            postal_code="M5H2N2",
            property_value=Decimal("600000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        
        await db_session.commit()

        # 2. Call API
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "550000.00", # High loan relative to income
                    "down_payment": "50000.00",
                    "amortization_years": 25,
                    "contract_rate": "5.0",
                    "property_tax_annual": "8000.00", # High tax
                    "heating_cost_monthly": "300.00",
                    "condo_fees_monthly": "500.00" # Condo fees
                }
            )

        # 3. Assertions
        assert response.status_code == 201 # API accepts request, logic rejects app
        data = response.json()
        
        assert data["decision"] == "REJECTED"
        assert "GDS" in data["rejection_reason"]
        assert data["gds_ratio"] > 39 # OSFI Limit

    async def test_get_decision_history(self, app: "FastAPI", db_session: AsyncSession):
        """
        Test retrieving the history of decisions for a specific borrower.
        """
        # 1. Setup Data
        borrower = Borrower(
            first_name="History",
            last_name="Test",
            sin_hash="hash789",
            date_of_birth="1992-02-02",
            credit_score=720,
            annual_income=Decimal("90000.00"),
            monthly_debt=Decimal("100.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="321 Elm St",
            city="Montreal",
            province="QC",
            postal_code="H2X1Y1",
            property_value=Decimal("400000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        await db_session.commit()

        # Create two decisions
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First Request
            await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "320000.00",
                    "down_payment": "80000.00",
                    "amortization_years": 20,
                    "contract_rate": "3.5",
                    "property_tax_annual": "3000.00",
                    "heating_cost_monthly": "120.00",
                    "condo_fees_monthly": "0.00"
                }
            )
            
            # Second Request (different loan)
            await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "350000.00",
                    "down_payment": "50000.00",
                    "amortization_years": 25,
                    "contract_rate": "4.0",
                    "property_tax_annual": "3000.00",
                    "heating_cost_monthly": "120.00",
                    "condo_fees_monthly": "0.00"
                }
            )

            # Get History
            response = await client.get(f"/api/v1/underwriting/decisions?borrower_id={borrower.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        # Check pagination or list structure
        assert all("decision" in item for item in data)

    async def test_invalid_input_validation(self, app: "FastAPI"):
        """
        Test that API rejects invalid payloads (422 Unprocessable Entity).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": 1,
                    # missing property_id
                    "loan_amount": "100000.00",
                }
            )
            
        assert response.status_code == 422

    async def test_cmhc_premium_calculation_integration(self, app: "FastAPI", db_session: AsyncSession):
        """
        Verify that the calculated insurance premium is saved correctly.
        Scenario: LTV 90% (Tier 3.10%).
        """
        borrower = Borrower(
            first_name="Premium",
            last_name="Check",
            sin_hash="hash999",
            date_of_birth="1988-08-08",
            credit_score=680,
            annual_income=Decimal("100000.00"),
            monthly_debt=Decimal("0.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="555 Bay St",
            city="Toronto",
            province="ON",
            postal_code="M5J2M2",
            property_value=Decimal("500000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        await db_session.commit()

        # Loan 450k on 500k value = 90% LTV
        # Premium 3.10% on 450k = 13,950
        loan_amount = Decimal("450000.00")
        expected_premium = loan_amount * Decimal("0.0310")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": str(loan_amount),
                    "down_payment": "50000.00",
                    "amortization_years": 25,
                    "contract_rate": "5.0",
                    "property_tax_annual": "5000.00",
                    "heating_cost_monthly": "150.00",
                    "condo_fees_monthly": "0.00"
                }
            )

        assert response.status_code == 201
        data = response.json()
        
        assert data["insurance_required"] is True
        # Compare as Decimal to avoid float precision issues in JSON parsing
        assert Decimal(data["insurance_premium"]) == expected_premium
```