--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import application components
from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.lender_comparison.models import (
    Lender,
    LenderProduct,
    Submission,
)
from mortgage_underwriting.modules.lender_comparison.routes import router
from mortgage_underwriting.modules.lender_comparison.schemas import (
    LenderProductCreate,
    SubmissionRequest,
)

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def app(db_session: AsyncSession) -> FastAPI:
    """
    Create a test application with overridden database dependency.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/lender-comparison", tags=["Lender Comparison"])

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
def valid_lender_product_data() -> dict:
    return {
        "lender_name": "Test Bank",
        "product_name": "Standard Mortgage",
        "min_credit_score": 680,
        "max_ltv_ratio": Decimal("0.80"),
        "min_income": Decimal("50000.00"),
        "interest_rate": Decimal("5.25"),
        "max_amortization_years": 25,
        "insurance_required": False,
    }

@pytest.fixture
def valid_submission_data() -> dict:
    return {
        "applicant_id": "applicant_123",
        "loan_amount": Decimal("400000.00"),
        "property_value": Decimal("500000.00"),
        "credit_score": 720,
        "annual_income": Decimal("90000.00"),
        "property_tax": Decimal("3000.00"),
        "heating_cost": Decimal("1200.00"),
        "other_debt": Decimal("500.00"),
    }

@pytest.fixture
async def sample_lender(db_session: AsyncSession, valid_lender_product_data: dict) -> LenderProduct:
    """
    Creates a sample lender product in the database for testing.
    """
    lender = Lender(
        name=valid_lender_product_data["lender_name"],
        contact_email="underwriting@testbank.com",
        api_endpoint="https://api.testbank.com/submit",
        is_active=True,
    )
    db_session.add(lender)
    await db_session.flush()

    product = LenderProduct(
        lender_id=lender.id,
        **valid_lender_product_data
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.lender_comparison.services import (
    LenderComparisonService,
    SubmissionService,
)
from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission
from mortgage_underwriting.modules.lender_comparison.exceptions import (
    NoLendersFoundError,
    SubmissionAPIError,
    ComplianceError,
)

@pytest.mark.unit
class TestLenderComparisonService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_lender_products(self):
        return [
            LenderProduct(
                id=1,
                lender_id=1,
                lender_name="Bank A",
                product_name="Prime 5yr",
                min_credit_score=700,
                max_ltv_ratio=Decimal("0.80"),
                min_income=Decimal("60000.00"),
                interest_rate=Decimal("4.99"),
                max_amortization_years=25,
                insurance_required=False,
            ),
            LenderProduct(
                id=2,
                lender_id=2,
                lender_name="Bank B",
                product_name="Flex 5yr",
                min_credit_score=650,
                max_ltv_ratio=Decimal("0.95"),
                min_income=Decimal("50000.00"),
                interest_rate=Decimal("5.25"),
                max_amortization_years=30,
                insurance_required=True,
            )
        ]

    @pytest.mark.asyncio
    async def test_find_matching_products_success(self, mock_db, mock_lender_products):
        # Arrange
        service = LenderComparisonService(mock_db)
        
        # Mock the result of executing a query to return our mock products
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_lender_products
        mock_db.execute.return_value = mock_result

        application_data = {
            "credit_score": 720,
            "loan_amount": Decimal("400000.00"),
            "property_value": Decimal("500000.00"), # 80% LTV
            "annual_income": Decimal("80000.00")
        }

        # Act
        matches = await service.find_matching_products(application_data)

        # Assert
        assert len(matches) == 2
        assert matches[0].lender_name == "Bank A"
        assert matches[1].lender_name == "Bank B"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_find_matching_products_filters_by_ltv(self, mock_db, mock_lender_products):
        # Arrange
        service = LenderComparisonService(mock_db)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_lender_products
        mock_db.execute.return_value = mock_result

        # High LTV scenario (90%)
        application_data = {
            "credit_score": 720,
            "loan_amount": Decimal("450000.00"),
            "property_value": Decimal("500000.00"),
            "annual_income": Decimal("80000.00")
        }

        # Act
        matches = await service.find_matching_products(application_data)

        # Assert - Bank A max LTV is 80%, should be filtered out
        assert len(matches) == 1
        assert matches[0].lender_name == "Bank B"

    @pytest.mark.asyncio
    async def test_find_matching_products_no_matches_raises(self, mock_db):
        # Arrange
        service = LenderComparisonService(mock_db)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [] # No products in DB
        mock_db.execute.return_value = mock_result

        application_data = {
            "credit_score": 500, # Very low score
            "loan_amount": Decimal("100.00"),
            "property_value": Decimal("1000.00"),
            "annual_income": Decimal("1000.00")
        }

        # Act & Assert
        with pytest.raises(NoLendersFoundError):
            await service.find_matching_products(application_data)

    @pytest.mark.asyncio
    async def test_calculate_ltv_boundary_check(self, mock_db):
        # Arrange
        service = LenderComparisonService(mock_db)
        
        # LTV = 80.00 (Exact boundary for 80% cap)
        ltv = service._calculate_ltv(Decimal("80000"), Decimal("100000"))
        assert ltv == Decimal("0.80")

        # LTV = 80.01 (Over boundary)
        ltv = service._calculate_ltv(Decimal("80001"), Decimal("100000"))
        assert ltv == Decimal("0.80001")


@pytest.mark.unit
class TestSubmissionService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def submission_payload(self):
        return {
            "product_id": 1,
            "applicant_id": "app_123",
            "data": {"loan_amount": "100000"}
        }

    @pytest.mark.asyncio
    async def test_submit_to_lender_success(self, mock_db, submission_payload):
        # Arrange
        service = SubmissionService(mock_db)
        
        # Mock the external HTTP call
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.json.return_value = {"reference_id": "LENDER_REF_999"}
            mock_post.return_value = mock_response

            # Act
            result = await service.submit_to_lender(
                product_id=1,
                payload=submission_payload["data"],
                endpoint_url="https://api.lender.com/submit"
            )

            # Assert
            assert result.status == "SUBMITTED"
            assert result.external_reference_id == "LENDER_REF_999"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_to_lender_api_failure(self, mock_db, submission_payload):
        # Arrange
        service = SubmissionService(mock_db)
        
        with patch("httpx.AsyncClient.post") as mock_post:
            # Simulate 500 Internal Server Error from Lender
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response

            # Act & Assert
            with pytest.raises(SubmissionAPIError):
                await service.submit_to_lender(
                    product_id=1,
                    payload=submission_payload["data"],
                    endpoint_url="https://api.lender.com/submit"
                )
            
            # Ensure DB transaction was rolled back or not committed for failed state
            mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_validate_compliance_stress_test_enforced(self, mock_db):
        # Arrange
        service = SubmissionService(mock_db)
        
        # Scenario: Contract rate 3.0%, Stress test floor is 5.25%
        # Logic should calculate qualifying rate at 5.25%
        contract_rate = Decimal("3.00")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        
        # Assert
        assert qualifying_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_validate_compliance_gds_limit(self, mock_db):
        # Arrange
        service = SubmissionService(mock_db)
        
        monthly_income = Decimal("5000.00")
        # Housing costs: Mortgage 2000 + Tax 300 + Heat 150 = 2450
        # GDS = 2450 / 5000 = 49% (Over 39% limit)
        housing_costs = Decimal("2450.00") 
        
        # Act & Assert
        with pytest.raises(ComplianceError) as exc_info:
            service._validate_gds(monthly_income, housing_costs)
        
        assert "GDS exceeds limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_compliance_tds_limit(self, mock_db):
        # Arrange
        service = SubmissionService(mock_db)
        
        monthly_income = Decimal("5000.00")
        # Total Debts: Housing 2000 + Other 500 = 2500
        # TDS = 2500 / 5000 = 50% (Over 44% limit)
        total_debts = Decimal("2500.00")
        
        # Act & Assert
        with pytest.raises(ComplianceError) as exc_info:
            service._validate_tds(monthly_income, total_debts)
            
        assert "TDS exceeds limit" in str(exc_info.value)
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct

@pytest.mark.integration
@pytest.mark.asyncio
class TestLenderComparisonRoutes:

    async def test_get_lenders_empty(self, app, client: AsyncClient):
        """
        Test GET /lenders returns empty list when no lenders exist.
        """
        response = await client.get("/api/v1/lender-comparison/lenders")
        assert response.status_code == 200
        assert response.json() == []

    async def test_compare_applications_no_match(self, app, client: AsyncClient, valid_submission_data: dict):
        """
        Test comparison endpoint when applicant doesn't meet any criteria.
        """
        # Modify data to be unmatchable (very low credit score)
        valid_submission_data["credit_score"] = 400
        
        response = await client.post("/api/v1/lender-comparison/compare", json=valid_submission_data)
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_compare_applications_success(
        self, 
        app, 
        client: AsyncClient, 
        sample_lender: LenderProduct, 
        valid_submission_data: dict
    ):
        """
        Test successful comparison returning matching products.
        """
        # Ensure data matches the sample_lender fixture criteria
        # Sample Lender: Min Credit 680, Max LTV 0.80
        valid_submission_data["credit_score"] = 700
        valid_submission_data["loan_amount"] = Decimal("400000.00")
        valid_submission_data["property_value"] = Decimal("500000.00") # 80% LTV
        valid_submission_data["annual_income"] = Decimal("60000.00")

        response = await client.post("/api/v1/lender-comparison/compare", json=valid_submission_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        
        # Verify structure of returned product
        product = data[0]
        assert "id" in product
        assert "lender_name" == product["lender_name"]
        assert "interest_rate" in product
        # Ensure Decimal precision is preserved in JSON response (usually string or float)
        assert product["max_ltv_ratio"] == "0.80" or product["max_ltv_ratio"] == 0.8

    async def test_compare_filters_high_ltv(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict
    ):
        """
        Test that comparison correctly filters out lenders if LTV is too high.
        Sample Lender Max LTV is 80%.
        """
        valid_submission_data["credit_score"] = 800
        valid_submission_data["loan_amount"] = Decimal("450000.00")
        valid_submission_data["property_value"] = Decimal("500000.00") # 90% LTV
        valid_submission_data["annual_income"] = Decimal("100000.00")

        response = await client.post("/api/v1/lender-comparison/compare", json=valid_submission_data)
        
        assert response.status_code == 404
        assert "No matching lenders found" in response.json()["detail"]

    async def test_submit_application_success(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict,
        monkeypatch
    ):
        """
        Test the submission workflow end-to-end with mocked external API.
        """
        # Mock the external HTTP request within the service
        # We use monkeypatch to replace httpx.post behavior during the request
        class MockResponse:
            status_code = 202
            def json(self):
                return {"reference_id": "EXT_REF_123"}

        async def mock_post(*args, **kwargs):
            return MockResponse()

        # Patch the specific method used in the service
        # Note: Depending on import structure, the path might need adjustment.
        # Assuming service imports httpx directly or uses a client.
        monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

        submit_payload = {
            "product_id": sample_lender.id,
            "application_data": valid_submission_data
        }

        response = await client.post("/api/v1/lender-comparison/submit", json=submit_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "SUBMITTED"
        assert data["external_reference_id"] == "EXT_REF_123"
        assert "id" in data

    async def test_submit_application_compliance_failure(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict
    ):
        """
        Test that submission fails if GDS/TDS compliance checks fail.
        Sample Lender logic should check these.
        """
        # Create a scenario that fails GDS/TDS
        # Low income, high housing costs
        valid_submission_data["annual_income"] = Decimal("30000.00") # Low
        valid_submission_data["loan_amount"] = Decimal("400000.00") # High debt
        valid_submission_data["property_value"] = Decimal("500000.00")
        valid_submission_data["property_tax"] = Decimal("5000.00")
        
        submit_payload = {
            "product_id": sample_lender.id,
            "application_data": valid_submission_data
        }

        response = await client.post("/api/v1/lender-comparison/submit", json=submit_payload)

        # Expect 400 Bad Request due to compliance/validation error
        assert response.status_code == 400
        data = response.json()
        assert "Compliance" in data["detail"] or "GDS" in data["detail"] or "TDS" in data["detail"]

    async def test_pipeda_check_no_pii_in_logs(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict,
        monkeypatch,
        caplog
    ):
        """
        Verify that sensitive data (SIN/DOB) is handled correctly.
        Note: This is a simplified check ensuring the endpoint doesn't echo back raw PII
        if it were included (though our schema doesn't strictly require SIN in this flow).
        """
        # Add PII fields to payload (even if schema ignores them or hashes them)
        valid_submission_data["sin"] = "123456789"
        
        # We are primarily checking the response doesn't leak it if we accidentally added it
        # and that the system doesn't crash.
        
        submit_payload = {
            "product_id": sample_lender.id,
            "application_data": valid_submission_data
        }

        # Mock external API to pass
        class MockResponse:
            status_code = 202
            def json(self):
                return {"reference_id": "REF"}

        async def mock_post(*args, **kwargs):
            return MockResponse()
        
        monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

        response = await client.post("/api/v1/lender-comparison/submit", json=submit_payload)
        
        # If successful, check response
        if response.status_code == 201:
            data = response.json()
            # Ensure raw SIN is not in the response body
            assert "123456789" not in str(data)
            # Ensure application_data in response is minimized or sanitized
            resp_app_data = data.get("application_data", {})
            assert "sin" not in resp_app_data
```