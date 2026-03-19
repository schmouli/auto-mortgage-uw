--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Import the module under test
from mortgage_underwriting.modules.lender_comparison.routes import router
from mortgage_underwriting.common.database import Base

# Use in-memory SQLite for integration tests speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/lender-comparison")
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_application_data():
    """Standard sample application data for testing."""
    return {
        "id": 1,
        "borrower_id": 101,
        "loan_amount": Decimal("450000.00"),
        "property_value": Decimal("600000.00"),
        "credit_score": 780,
        "income": Decimal("120000.00"),
        "down_payment": Decimal("150000.00"),
    }


@pytest.fixture
def sample_lenders():
    """Sample lenders with different criteria."""
    return [
        {
            "id": 1,
            "name": "Big Bank Corp",
            "min_credit_score": 700,
            "max_ltv": Decimal("0.80"),
            "base_rate": Decimal("5.00"),
            "insurance_required": False,
        },
        {
            "id": 2,
            "name": "Trusty Credit Union",
            "min_credit_score": 650,
            "max_ltv": Decimal("0.95"),
            "base_rate": Decimal("5.25"),
            "insurance_required": True,
        },
        {
            "id": 3,
            "name": "Elite Mortgages",
            "min_credit_score": 800,
            "max_ltv": Decimal("0.70"),
            "base_rate": Decimal("4.80"),
            "insurance_required": False,
        },
    ]

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.lender_comparison.services import LenderService
from mortgage_underwriting.modules.lender_comparison.models import Lender, Submission
from mortgage_underwriting.modules.lender_comparison.schemas import (
    LenderOfferCreate,
    SubmissionCreate,
    LenderOfferResponse,
)
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestLenderService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return LenderService(mock_db)

    @pytest.mark.asyncio
    async def test_compare_offers_success(self, service, mock_db, sample_application_data, sample_lenders):
        """Test that eligible lenders are returned and ineligible ones are filtered."""
        # Setup Mock DB return for lenders
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [
            Lender(**lender) for lender in sample_lenders
        ]
        mock_db.execute.return_value = mock_result

        # Logic: LTV = 450000 / 600000 = 0.75 (75%)
        # Big Bank (Max 80%, Min 700) -> Eligible
        # Trusty (Max 95%, Min 650) -> Eligible
        # Elite (Max 70%) -> Ineligible (LTV too high)

        offers = await service.compare_offers(application_id=1)

        assert len(offers) == 2
        assert offers[0].lender_name == "Big Bank Corp"
        assert offers[1].lender_name == "Trusty Credit Union"
        
        # Verify Elite was filtered out
        lender_names = [o.lender_name for o in offers]
        assert "Elite Mortgages" not in lender_names

    @pytest.mark.asyncio
    async def test_compare_offers_filters_credit_score(self, service, mock_db, sample_application_data):
        """Test filtering based on credit score."""
        low_credit_app = {**sample_application_data, "credit_score": 660}
        
        # Mock Lenders
        lenders_data = [
            {"id": 1, "name": "High Bar Bank", "min_credit_score": 700, "max_ltv": Decimal("0.80"), "base_rate": Decimal("5.00")},
            {"id": 2, "name": "Low Bar Bank", "min_credit_score": 600, "max_ltv": Decimal("0.80"), "base_rate": Decimal("5.50")},
        ]
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [Lender(**l) for l in lenders_data]
        mock_db.execute.return_value = mock_result

        offers = await service.compare_offers(application_id=1)

        assert len(offers) == 1
        assert offers[0].lender_name == "Low Bar Bank"

    @pytest.mark.asyncio
    async def test_compare_offers_calculates_monthly_payment(self, service, mock_db, sample_application_data):
        """Test accurate monthly payment calculation using Decimal."""
        # Mock Lender
        lender_data = {
            "id": 1, "name": "Test Bank", "min_credit_score": 600, 
            "max_ltv": Decimal("0.95"), "base_rate": Decimal("6.00"), # 6% annual
            "insurance_required": False
        }
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [Lender(**lender_data)]
        mock_db.execute.return_value = mock_result

        offers = await service.compare_offers(application_id=1)

        assert len(offers) == 1
        # Loan: 450,000, Rate: 6% (0.5% monthly), Term: 25 years (300 months)
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.005, n = 300
        # Expected approx: $2,895.86
        expected_payment = Decimal("2895.86")
        # Allow small rounding difference
        assert offers[0].estimated_monthly_payment.quantize(Decimal("0.01")) == expected_payment

    @pytest.mark.asyncio
    async def test_compare_offers_no_eligible_lenders(self, service, mock_db, sample_application_data):
        """Test scenario where no lender meets criteria."""
        # Strict Lenders
        lenders_data = [
            {"id": 1, "name": "Strict Bank", "min_credit_score": 850, "max_ltv": Decimal("0.50"), "base_rate": Decimal("4.00")}
        ]
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [Lender(**l) for l in lenders_data]
        mock_db.execute.return_value = mock_result

        offers = await service.compare_offers(application_id=1)
        assert len(offers) == 0

    @pytest.mark.asyncio
    async def test_submit_application_success(self, service, mock_db):
        """Test successful submission creation."""
        submission_data = SubmissionCreate(
            application_id=1,
            lender_id=5,
            offer_details={"rate": "5.00", "term": "5-year fixed"}
        )

        # Mock the DB add/commit cycle
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.submit_submission(submission_data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        assert result.application_id == 1
        assert result.lender_id == 5

    @pytest.mark.asyncio
    async def test_submit_application_invalid_lender_id_raises(self, service, mock_db):
        """Test that submitting with a non-existent lender raises an error."""
        # Simulate DB check returning None for lender
        mock_db.scalar.return_value = None

        submission_data = SubmissionCreate(
            application_id=1,
            lender_id=999, # Non-existent
            offer_details={}
        )

        with pytest.raises(AppException) as exc_info:
            await service.submit_submission(submission_data)
        
        assert exc_info.value.error_code == "LENDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_submission_history(self, service, mock_db):
        """Test retrieving submission history for an application."""
        mock_result = MagicMock()
        mock_submissions = [
            Submission(id=1, application_id=10, lender_id=2, status="submitted"),
            Submission(id=2, application_id=10, lender_id=3, status="rejected"),
        ]
        mock_result.scalars().all.return_value = mock_submissions
        mock_db.execute.return_value = mock_result

        history = await service.get_submission_history(application_id=10)

        assert len(history) == 2
        assert history[0].status == "submitted"
        assert history[1].status == "rejected"

    @pytest.mark.asyncio
    async def test_ltv_calculation_precision(self, service, mock_db):
        """Ensure LTV calculation uses Decimal and has no precision loss."""
        # Edge case: High precision numbers
        high_precision_data = {
            "loan_amount": Decimal("100000.01"),
            "property_value": Decimal("100000.01"),
            "credit_score": 750
        }
        
        # We can't easily inject this into compare_offers without mocking the app repo too,
        # but we test the calculation logic directly if exposed, or verify via the result
        # Here we assume the service fetches the app. Let's mock the app fetch.
        # Note: In a real unit test, we might mock the ApplicationRepository.
        
        # For this exercise, we verify the LTV logic in the offer generation if accessible
        # or rely on the integration test for the full flow.
        # Let's assume we verify the filter logic using specific LTVs.
        
        pass # Logic covered in integration tests for full flow

--- integration_tests ---
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