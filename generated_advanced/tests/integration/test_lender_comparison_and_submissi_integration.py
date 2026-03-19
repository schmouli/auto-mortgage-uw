import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.lender_comparison.models import Lender, Submission
from mortgage_underwriting.modules.application.models import Application # Assuming cross-module dependency
from mortgage_underwriting.modules.borrower.models import Borrower


@pytest.mark.integration
@pytest.mark.asyncio
class TestLenderComparisonAPI:

    async def test_compare_lenders_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test the full comparison workflow via API."""
        
        # 1. Setup Data in DB
        # Create Borrower
        borrower = Borrower(
            id=1, 
            first_name="John", 
            last_name="Doe", 
            credit_score=720, 
            sin_hash="hash123", 
            dob_encrypted="enc123"
        )
        db_session.add(borrower)
        
        # Create Application
        application = Application(
            id=1,
            borrower_id=1,
            loan_amount=Decimal("300000.00"),
            property_value=Decimal("400000.00"), # 75% LTV
            income=Decimal("90000.00"),
            status="draft"
        )
        db_session.add(application)

        # Create Lenders
        lender_a = Lender(
            id=1,
            name="Lender A",
            min_credit_score=700,
            max_ltv=Decimal("0.80"), # Eligible
            base_rate=Decimal("5.00")
        )
        lender_b = Lender(
            id=2,
            name="Lender B",
            min_credit_score=750, # Ineligible (Score 720)
            max_ltv=Decimal("0.80"),
            base_rate=Decimal("4.90")
        )
        lender_c = Lender(
            id=3,
            name="Lender C",
            min_credit_score=600,
            max_ltv=Decimal("0.70"), # Ineligible (LTV 75%)
            base_rate=Decimal("5.10")
        )
        db_session.add_all([lender_a, lender_b, lender_c])
        await db_session.commit()

        # 2. Call API
        response = await client.get(f"/api/v1/lender-comparison/applications/1/compare")

        # 3. Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert "offers" in data
        offers = data["offers"]
        
        # Only Lender A should be eligible
        assert len(offers) == 1
        assert offers[0]["lender_name"] == "Lender A"
        assert offers[0]["estimated_monthly_payment"] is not None
        # Check Decimal serialization (string)
        assert isinstance(offers[0]["interest_rate"], str)

    async def test_submit_application_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test submitting an application to a specific lender."""
        
        # Setup
        lender = Lender(id=10, name="Test Lender", min_credit_score=600, max_ltv=Decimal("0.95"), base_rate=Decimal("5.00"))
        db_session.add(lender)
        await db_session.commit()

        payload = {
            "application_id": 1,
            "lender_id": 10,
            "offer_details": {"rate": "5.00", "monthly_payment": "2000.00"}
        }

        # Submit
        response = await client.post("/api/v1/lender-comparison/submissions", json=payload)

        # Assertions
        assert response.status_code == 201
        data = response.json()
        assert data["lender_id"] == 10
        assert data["status"] == "pending"
        assert "id" in data

        # Verify DB State
        result = await db_session.execute(select(Submission).where(Submission.id == data["id"]))
        submission = result.scalar_one()
        assert submission is not None
        assert submission.application_id == 1

    async def test_get_submission_history(self, client: AsyncClient, db_session: AsyncSession):
        """Test retrieving history."""
        # Setup existing submission
        sub = Submission(id=99, application_id=2, lender_id=1, status="approved")
        db_session.add(sub)
        await db_session.commit()

        response = await client.get(f"/api/v1/lender-comparison/applications/2/submissions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == 99
        assert data[0]["status"] == "approved"

    async def test_ltv_boundary_check(self, client: AsyncClient, db_session: AsyncSession):
        """Test LTV filtering at exact boundaries."""
        # Setup Application with exactly 80% LTV
        # Loan 400k, Value 500k = 80%
        borrower = Borrower(id=2, first_name="Jane", last_name="Smith", credit_score=700, sin_hash="h", dob_encrypted="e")
        app = Application(id=3, borrower_id=2, loan_amount=Decimal("400000.00"), property_value=Decimal("500000.00"), income=Decimal("80000.00"), status="draft")
        
        # Lender with Max LTV 80% (Should be included)
        lender_80 = Lender(id=4, name="Lender 80", min_credit_score=600, max_ltv=Decimal("0.80"), base_rate=Decimal("5.00"))
        # Lender with Max LTV 79.99% (Should be excluded)
        lender_79 = Lender(id=5, name="Lender 79", min_credit_score=600, max_ltv=Decimal("0.7999"), base_rate=Decimal("5.00"))
        
        db_session.add_all([borrower, app, lender_80, lender_79])
        await db_session.commit()

        response = await client.get(f"/api/v1/lender-comparison/applications/3/compare")
        data = response.json()
        
        assert len(data["offers"]) == 1
        assert data["offers"][0]["lender_name"] == "Lender 80"

    async def test_invalid_submission_request(self, client: AsyncClient):
        """Test validation error on bad request."""
        payload = {
            "application_id": -1, # Invalid ID
            "lender_id": 999,
            "offer_details": {}
        }
        
        response = await client.post("/api/v1/lender-comparison/submissions", json=payload)
        
        # Assuming Pydantic validation or Service logic catches this
        # If it's a FK constraint, it might be 500 or 404 depending on implementation
        # Here we test basic schema validation if applicable, or service rejection
        assert response.status_code in [400, 404, 422]

    async def test_high_ltv_insurance_requirement(self, client: AsyncClient, db_session: AsyncSession):
        """Verify offers indicate insurance requirement correctly based on LTV."""
        # 95% LTV Application
        borrower = Borrower(id=3, first_name="Bob", last_name="Jones", credit_score=700, sin_hash="h", dob_encrypted="e")
        app = Application(id=4, borrower_id=3, loan_amount=Decimal("475000.00"), property_value=Decimal("500000.00"), income=Decimal("80000.00"), status="draft")
        
        lender = Lender(id=6, name="High Ratio Lender", min_credit_score=600, max_ltv=Decimal("0.95"), base_rate=Decimal("5.00"), insurance_required=True)
        
        db_session.add_all([borrower, app, lender])
        await db_session.commit()

        response = await client.get(f"/api/v1/lender-comparison/applications/4/compare")
        data = response.json()
        
        assert len(data["offers"]) == 1
        # The response should likely indicate if insurance is needed/premium
        # Assuming the schema includes this field
        assert data["offers"][0]["insurance_required"] is True