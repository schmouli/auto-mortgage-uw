--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from unittest.mock import AsyncMock, MagicMock

# Import common configuration and base models
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.lender_comparison.models import (
    Lender,
    LenderProduct,
    Submission,
    SubmissionStatus,
)
from mortgage_underwriting.modules.lender_comparison.schemas import (
    LenderProductCreate,
    ComparisonRequest,
    SubmissionRequest,
)

# Database Setup for Testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def sample_lender_data():
    return {
        "name": "Test Bank",
        "contact_email": "underwriting@testbank.com",
        "api_endpoint": "https://api.testbank.com/submit",
        "is_active": True,
    }

@pytest.fixture
def sample_product_data():
    return {
        "lender_id": 1, # Assumed ID after creation
        "product_name": "Standard 5-Year Fixed",
        "rate": Decimal("4.85"),
        "term_months": 60,
        "max_ltv": Decimal("80.00"),
        "min_credit_score": 680,
        "insurance_required": False,
    }

@pytest.fixture
def sample_comparison_request():
    return ComparisonRequest(
        loan_amount=Decimal("450000.00"),
        property_value=Decimal("550000.00"),
        credit_score=720,
        province="ON",
        income=Decimal("120000.00"),
        amortization_years=25,
    )

@pytest.fixture
def mock_http_client():
    """
    Mocks the external httpx.AsyncClient used for submitting to lenders.
    """
    with pytest.mock.patch("httpx.AsyncClient") as mock:
        client = MagicMock()
        client.post = AsyncMock()
        client.post.return_value = MagicMock(
            status_code=200, json=lambda: {"application_id": "EXT-12345", "status": "received"}
        )
        mock.return_value = client
        yield client
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission, SubmissionStatus
from mortgage_underwriting.modules.lender_comparison.services import ComparisonService, SubmissionService
from mortgage_underwriting.modules.lender_comparison.exceptions import LenderUnavailableError, SubmissionFailedError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestComparisonService:
    
    @pytest.mark.asyncio
    async def test_compare_products_success(self, db_session, sample_lender_data, sample_product_data, sample_comparison_request):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        # Create two products
        prod1 = LenderProduct(**sample_product_data, lender_id=lender.id, rate=Decimal("5.00"))
        prod2 = LenderProduct(**sample_product_data, lender_id=lender.id, rate=Decimal("4.50"), product_name="Best Rate")
        db_session.add_all([prod1, prod2])
        await db_session.commit()
        
        service = ComparisonService(db_session)
        
        # Act
        results = await service.compare(sample_comparison_request)
        
        # Assert
        assert len(results) == 2
        # Results should be sorted by rate (ascending)
        assert results[0].rate == Decimal("4.50")
        assert results[1].rate == Decimal("5.00")
        assert results[0].monthly_payment > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_compare_filters_by_ltv(self, db_session, sample_lender_data, sample_product_data):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        # Product with low max LTV
        low_ltv_prod = LenderProduct(**sample_product_data, lender_id=lender.id, max_ltv=Decimal("70.00"))
        db_session.add(low_ltv_prod)
        await db_session.commit()
        
        service = ComparisonService(db_session)
        
        # Request with 80% LTV (Loan 400k / Value 500k)
        request = MagicMock(
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            credit_score=750,
            province="BC",
            amortization_years=25
        )
        
        # Act
        results = await service.compare(request)
        
        # Assert
        assert len(results) == 0 # Should be filtered out because 80% > 70%

    @pytest.mark.asyncio
    async def test_compare_no_products_found(self, db_session):
        service = ComparisonService(db_session)
        request = MagicMock(
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("200000.00"),
            credit_score=800,
            province="ON",
            amortization_years=20
        )
        
        results = await service.compare(request)
        assert results == []

    @pytest.mark.asyncio
    async def test_calculate_monthly_payment_accuracy(self):
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # P=100k, i=0.05/12, n=300 (25y)
        # Expected approx: 584.59
        principal = Decimal("100000.00")
        annual_rate = Decimal("0.05")
        months = 300
        
        payment = ComparisonService._calculate_payment(principal, annual_rate, months)
        
        # Using a rough delta for decimal comparison
        assert abs(payment - Decimal("584.59")) < Decimal("0.01")

@pytest.mark.unit
class TestSubmissionService:

    @pytest.mark.asyncio
    async def test_submit_to_lender_success(self, db_session, sample_lender_data, mock_http_client):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="Fixed 5yr",
            rate=Decimal("4.5"),
            term_months=60,
            max_ltv=Decimal("80.00"),
            min_credit_score=600,
            insurance_required=False
        )
        db_session.add(product)
        await db_session.commit()
        
        submission_data = MagicMock(
            product_id=product.id,
            application_id="APP-999",
            borrower_json={"name": "John Doe"}
        )
        
        service = SubmissionService(db_session)
        
        # Act
        result = await service.submit(submission_data)
        
        # Assert
        assert result.status == SubmissionStatus.SUBMITTED
        assert result.external_reference_id == "EXT-12345"
        
        # Verify DB record
        await db_session.refresh(result)
        assert result.created_at is not None
        
        # Verify external call was made
        mock_http_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_to_lender_network_error(self, db_session, sample_lender_data):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="Fixed 5yr",
            rate=Decimal("4.5"),
            term_months=60,
            max_ltv=Decimal("80.00"),
            min_credit_score=600,
            insurance_required=False
        )
        db_session.add(product)
        await db_session.commit()
        
        submission_data = MagicMock(
            product_id=product.id,
            application_id="APP-999",
            borrower_json={"name": "John Doe"}
        )
        
        # Mock httpx to raise an exception
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(side_effect=Exception("Network Down"))
            MockClient.return_value = mock_instance
            
            service = SubmissionService(db_session)
            
            # Act & Assert
            with pytest.raises(SubmissionFailedError):
                await service.submit(submission_data)
            
            # Verify status in DB is FAILED
            stmt = select(Submission).where(Submission.application_id == "APP-999")
            res = await db_session.execute(stmt)
            record = res.scalar_one()
            assert record.status == SubmissionStatus.FAILED

    @pytest.mark.asyncio
    async def test_submit_product_not_found(self, db_session):
        service = SubmissionService(db_session)
        submission_data = MagicMock(
            product_id=9999, # Non-existent
            application_id="APP-000",
            borrower_json={}
        )
        
        with pytest.raises(AppException):
            await service.submit(submission_data)
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from mortgage_underwriting.modules.lender_comparison.routes import router
from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct
from fastapi import FastAPI

@pytest.fixture(scope="function")
def app(db_session):
    """
    Create a test FastAPI app with the router included.
    """
    app = FastAPI()
    app.include_router(router)
    
    # Dependency override for the database session
    # This ensures the router uses our test session
    async def get_db_override():
        yield db_session
        
    app.dependency_overrides[router.dependency_cache.get("get_async_session")] = get_db_override
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestLenderComparisonEndpoints:

    async def test_get_lenders_empty(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/lender-comparison/lenders")
            assert response.status_code == 200
            assert response.json() == []

    async def test_get_lenders_with_data(self, app: FastAPI, db_session):
        # Setup Data
        lender = Lender(name="Big Bank", contact_email="u@bb.com", api_endpoint="http://bb.com", is_active=True)
        db_session.add(lender)
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/lender-comparison/lenders")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Big Bank"

    async def test_compare_endpoint_workflow(self, app: FastAPI, db_session):
        # Setup: Add Lender and Product
        lender = Lender(name="Rate Setter", contact_email="u@rs.com", api_endpoint="http://rs.com", is_active=True)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="5yr Fixed",
            rate=Decimal("4.00"),
            term_months=60,
            max_ltv=Decimal("95.00"),
            min_credit_score=650,
            insurance_required=True
        )
        db_session.add(product)
        await db_session.commit()
        
        payload = {
            "loan_amount": "300000.00",
            "property_value": "400000.00",
            "credit_score": 700,
            "province": "ON",
            "income": "90000.00",
            "amortization_years": 25
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/compare", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0
            
            # Check response structure
            offer = data[0]
            assert "lender_name" in offer
            assert "product_name" in offer
            assert "monthly_payment" in offer
            assert Decimal(offer["rate"]) == Decimal("4.00")

    async def test_compare_validation_error(self, app: FastAPI):
        # Invalid payload (missing fields)
        payload = {
            "loan_amount": "100000"
            # Missing property_value, etc.
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/compare", json=payload)
            assert response.status_code == 422 # Validation Error

@pytest.mark.integration
@pytest.mark.asyncio
class TestSubmissionEndpoints:

    async def test_submit_endpoint_success(self, app: FastAPI, db_session):
        # Setup
        lender = Lender(name="Direct Lender", contact_email="u@dl.com", api_endpoint="http://dl.com", is_active=True)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="Var Rate",
            rate=Decimal("3.50"),
            term_months=60,
            max_ltv=Decimal("80.00"),
            min_credit_score=700,
            insurance_required=False
        )
        db_session.add(product)
        await db_session.commit()
        
        payload = {
            "product_id": product.id,
            "application_id": "INT-TEST-001",
            "borrower_data": {"sin": "999999999", "dob": "1990-01-01"} # PII that must be handled
        }
        
        # Mock the external call inside the integration test
        # We want to test the API controller logic, not the real external API
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"ref": "EXT-REF-123"}
            
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            MockClient.return_value = mock_http
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/lender-comparison/submit", json=payload)
                
                assert response.status_code == 201
                data = response.json()
                assert data["status"] == "submitted"
                assert data["external_reference_id"] == "EXT-REF-123"
                
                # Verify Audit trail in DB
                from mortgage_underwriting.modules.lender_comparison.models import Submission
                from sqlalchemy import select
                
                stmt = select(Submission).where(Submission.application_id == "INT-TEST-001")
                res = await db_session.execute(stmt)
                sub = res.scalar_one()
                
                assert sub.created_at is not None
                # Ensure PII is not stored in plain text if the service handles encryption
                # (Assuming service logic handles this, we check existence here)

    async def test_submit_invalid_product(self, app: FastAPI, db_session):
        payload = {
            "product_id": 9999,
            "application_id": "INT-TEST-002",
            "borrower_data": {}
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/submit", json=payload)
            assert response.status_code == 404
```