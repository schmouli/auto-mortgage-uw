--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric, Boolean, DateTime, func, Integer
from datetime import datetime
import uuid

# Base setup for testing
class Base(DeclarativeBase):
    pass

# Mock Models matching the module structure
class LenderModel(Base):
    __tablename__ = "lenders"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class LenderProductModel(Base):
    __tablename__ = "lender_products"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lender_id: Mapped[int] = mapped_column(Integer, index=True)
    product_name: Mapped[str] = mapped_column(String(100))
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4)) # e.g. 0.0450
    max_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 2)) # e.g. 80.00
    min_credit_score: Mapped[int] = mapped_column(Integer)
    insurance_required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SubmissionModel(Base):
    __tablename__ = "submissions"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(String(36))
    lender_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(100)) # FINTRAC compliance

# Database Fixture
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Using in-memory SQLite for speed and isolation
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# FastAPI App Fixture
@pytest.fixture
def app():
    from fastapi import FastAPI
    from mortgage_underwriting.modules.lender_comparison.routes import router
    from mortgage_underwriting.common.database import get_async_session
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/lender-comparison", tags=["Lender Comparison"])
    
    # Override dependency for testing
    async def override_get_db():
        # This is a simplified override; in real test we might pass the session fixture
        # But for integration test pattern provided, we use the client fixture
        pass 
    
    return app

# Data Fixtures
@pytest.fixture
def sample_lender(db_session: AsyncSession):
    lender = LenderModel(name="Test Bank", is_active=True)
    db_session.add(lender)
    await db_session.commit()
    await db_session.refresh(lender)
    return lender

@pytest.fixture
def sample_products(sample_lender, db_session: AsyncSession):
    products = [
        LenderProductModel(
            lender_id=sample_lender.id,
            product_name="Standard Variable",
            rate=Decimal("0.0500"),
            max_ltv=Decimal("80.00"),
            min_credit_score=650
        ),
        LenderProductModel(
            lender_id=sample_lender.id,
            product_name="High Ratio Fixed",
            rate=Decimal("0.0550"),
            max_ltv=Decimal("95.00"),
            min_credit_score=680
        )
    ]
    for p in products:
        db_session.add(p)
    await db_session.commit()
    return products

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test_token"}

@pytest.fixture
def comparison_payload():
    return {
        "loan_amount": "450000.00",
        "property_value": "500000.00", # 90% LTV
        "credit_score": 700,
        "province": "ON",
        "amortization_years": 25
    }

@pytest.fixture
def submission_payload():
    return {
        "application_id": str(uuid.uuid4()),
        "lender_id": 1,
        "product_id": 1
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Module Imports
from mortgage_underwriting.modules.lender_comparison.services import LenderComparisonService, SubmissionService
from mortgage_underwriting.modules.lender_comparison.exceptions import LenderNotFoundException, SubmissionValidationError
from mortgage_underwriting.modules.lender_comparison.schemas import LenderProductResponse, SubmissionResponse

# Mock Models
from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission

@pytest.mark.unit
class TestLenderComparisonService:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_products(self):
        return [
            LenderProduct(
                id=1,
                lender_id=1,
                product_name="Prime 5yr",
                rate=Decimal("0.0499"),
                max_ltv=Decimal("80.00"),
                min_credit_score=680,
                insurance_required=False
            ),
            LenderProduct(
                id=2,
                lender_id=1,
                product_name="High Ratio",
                rate=Decimal("0.0520"),
                max_ltv=Decimal("95.00"),
                min_credit_score=650,
                insurance_required=True
            )
        ]

    @pytest.mark.asyncio
    async def test_compare_lenders_filters_by_ltv(self, mock_db, mock_products):
        # Setup Mock Result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_products
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # Request: 90% LTV
        result = await service.compare_lenders(
            loan_amount=Decimal("450000"),
            property_value=Decimal("500000"),
            credit_score=700,
            province="ON"
        )

        # Assertions
        assert len(result) == 2 # Both valid for 90% LTV
        # Verify the mock was called with correct filtering logic (conceptually)
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compare_lenders_excludes_high_ltv_products(self, mock_db, mock_products):
        # Setup Mock Result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_products
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # Request: 85% LTV
        result = await service.compare_lenders(
            loan_amount=Decimal("425000"),
            property_value=Decimal("500000"),
            credit_score=700,
            province="ON"
        )

        # Assertions
        assert len(result) == 1
        assert result[0].max_ltv >= Decimal("85.00")

    @pytest.mark.asyncio
    async def test_compare_lenders_calculates_monthly_payment(self, mock_db):
        # Mock single product
        mock_product = LenderProduct(
            id=1,
            lender_id=1,
            product_name="Fixed",
            rate=Decimal("0.0500"), # 5%
            max_ltv=Decimal("80.00"),
            min_credit_score=600,
            insurance_required=False
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_product]
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # 100k loan, 5% annual, 25 years (300 months)
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05/12 = 0.00416666
        # n = 300
        # Expected approx 584.59
        result = await service.compare_lenders(
            loan_amount=Decimal("100000"),
            property_value=Decimal("125000"),
            credit_score=650,
            province="BC"
        )

        assert len(result) == 1
        # Check calculation exists and is Decimal
        assert result[0].estimated_monthly_payment is not None
        assert isinstance(result[0].estimated_monthly_payment, Decimal)
        # Rough check: 584.59
        assert result[0].estimated_monthly_payment > Decimal("580.00")
        assert result[0].estimated_monthly_payment < Decimal("590.00")

    @pytest.mark.asyncio
    async def test_compare_lenders_includes_insurance_premium(self, mock_db):
        # Mock product requiring insurance (CMHC)
        # LTV 90% -> Premium 3.10% (CMHC Rule)
        # Loan 100k. Premium 3100. Total loan 103100.
        mock_product = LenderProduct(
            id=1,
            lender_id=1,
            product_name="Insured",
            rate=Decimal("0.0500"),
            max_ltv=Decimal("95.00"),
            min_credit_score=600,
            insurance_required=True
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_product]
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # 90k loan, 100k value -> 90% LTV
        result = await service.compare_lenders(
            loan_amount=Decimal("90000"),
            property_value=Decimal("100000"),
            credit_score=650,
            province="ON"
        )
        
        assert len(result) == 1
        # Payment should be higher than non-insured 90k loan due to premium capitalization
        # Payment for 90k @ 5% is ~526. 
        # With 3.1% premium (2790), loan is 92790. Payment ~542.
        assert result[0].estimated_monthly_payment > Decimal("540.00")

    @pytest.mark.asyncio
    async def test_compare_lenders_no_results(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        result = await service.compare_lenders(
            loan_amount=Decimal("500000"),
            property_value=Decimal("500000"), # 100% LTV
            credit_score=800,
            province="ON"
        )

        assert len(result) == 0

@pytest.mark.unit
class TestSubmissionService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_lender_repo(self):
        with patch('mortgage_underwriting.modules.lender_comparison.services.LenderRepository') as repo:
            yield repo

    @pytest.mark.asyncio
    async def test_submit_application_success(self, mock_db, mock_lender_repo):
        # Setup mocks
        mock_lender = MagicMock()
        mock_lender.id = 1
        mock_lender.name = "Big Bank"
        mock_lender.api_endpoint = "https://bigbank.com/api"
        
        mock_lender_repo.return_value.get_by_id.return_value = mock_lender

        service = SubmissionService(mock_db)
        app_id = uuid4()
        
        # Mock external API call
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"reference": "EXT-123"}

            result = await service.submit_application(
                application_id=str(app_id),
                lender_id=1,
                user_id="user_123"
            )

            # Assertions
            assert isinstance(result, SubmissionResponse)
            assert result.status == "SUBMITTED"
            assert result.lender_name == "Big Bank"
            
            # FINTRAC: Verify audit fields
            mock_db.add.assert_called_once()
            added_obj = mock_db.add.call_args[0][0]
            assert isinstance(added_obj, Submission)
            assert added_obj.created_by == "user_123"
            assert added_obj.application_id == str(app_id)
            
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_application_lender_not_found(self, mock_db, mock_lender_repo):
        mock_lender_repo.return_value.get_by_id.return_value = None
        
        service = SubmissionService(mock_db)
        
        with pytest.raises(LenderNotFoundException) as exc_info:
            await service.submit_application(
                application_id=str(uuid4()),
                lender_id=999,
                user_id="user_123"
            )
        
        assert "Lender 999 not found" in str(exc_info.value)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_application_external_api_failure(self, mock_db, mock_lender_repo):
        mock_lender = MagicMock()
        mock_lender.id = 1
        mock_lender.name = "Bad Bank"
        mock_lender.api_endpoint = "https://badbank.com/api"
        mock_lender_repo.return_value.get_by_id.return_value = mock_lender

        service = SubmissionService(mock_db)

        with patch('httpx.AsyncClient.post') as mock_post:
            # Simulate 500 Internal Server Error
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Error"

            with pytest.raises(SubmissionValidationError) as exc_info:
                await service.submit_application(
                    application_id=str(uuid4()),
                    lender_id=1,
                    user_id="user_123"
                )
            
            assert "Failed to submit" in str(exc_info.value)
            # Verify DB transaction was not committed for failed submission
            mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_application_sanitizes_pii(self, mock_db, mock_lender_repo):
        # PIPEDA Check: Ensure SIN is not sent to external lender if payload contains it
        mock_lender = MagicMock()
        mock_lender.id = 1
        mock_lender.name = "Secure Bank"
        mock_lender.api_endpoint = "https://secure.com/api"
        mock_lender_repo.return_value.get_by_id.return_value = mock_lender

        service = SubmissionService(mock_db)

        with patch('mortgage_underwriting.modules.lender_comparison.services.get_application_details') as get_app:
            # Mock app details containing PII
            get_app.return_value = {
                "id": str(uuid4()),
                "sin": "123-456-789", # SENSITIVE
                "income": "100000",
                "first_name": "John",
                "last_name": "Doe"
            }

            with patch('httpx.AsyncClient.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"ref": "123"}

                await service.submit_application(
                    application_id=str(uuid4()),
                    lender_id=1,
                    user_id="user_123"
                )

                # Check the payload sent to external API
                call_args = mock_post.call_args
                sent_data = call_args.kwargs.get('json') or call_args[1].get('json')
                
                # Assert SIN is NOT in the payload
                assert "sin" not in sent_data
                assert "123-456-789" not in str(sent_data)
                # Assert normal fields are present
                assert sent_data["first_name"] == "John"
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestLenderComparisonRoutes:

    async def test_compare_lenders_happy_path(self, app, db_session: AsyncSession, sample_lender, sample_products):
        # Override dependency to use our test session
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/compare", json={
                "loan_amount": "450000.00",
                "property_value": "500000.00", # 90% LTV
                "credit_score": 700,
                "province": "ON",
                "amortization_years": 25
            })
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return only the High Ratio product (max_ltv 95%)
            # The Standard Variable product has max_ltv 80%, so it should be excluded
            assert len(data) == 1
            assert data[0]["product_name"] == "High Ratio Fixed"
            assert data[0]["rate"] == "0.0550"
            assert "estimated_monthly_payment" in data[0]
            # Check PII is not leaked (though this endpoint doesn't request SIN, it's good practice)
            assert "sin" not in str(data)

    async def test_compare_lenders_empty_result(self, app, db_session: AsyncSession, sample_lender, sample_products):
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Request 96% LTV, but max product is 95%
            response = await client.post("/api/v1/lender-comparison/compare", json={
                "loan_amount": "480000.00",
                "property_value": "500000.00",
                "credit_score": 800,
                "province": "BC",
                "amortization_years": 30
            })
            
            assert response.status_code == 200
            assert response.json() == []

    async def test_compare_lenders_validation_error(self, app, db_session: AsyncSession):
        def override_get_db():
            yield db_session
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Invalid input (negative amount)
            response = await client.post("/api/v1/lender-comparison/compare", json={
                "loan_amount": "-100",
                "property_value": "500000.00",
                "credit_score": 700,
                "province": "ON",
                "amortization_years": 25
            })
            
            assert response.status_code == 422 # Validation Error

    async def test_submit_application_workflow(self, app, db_session: AsyncSession, sample_lender, sample_products):
        def override_get_db():
            yield db_session
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        app_id = str(uuid4())
        
        # Mock the external lender API call within the integration test
        # We are testing the route + service + DB, but not the real external bank
        with pytest.MonkeyPatch().context() as m:
            # Mocking httpx.post inside the service layer
            # Note: In a real scenario, we might use a respx mock for exact URL matching
            async def mock_post(*args, **kwargs):
                class MockResponse:
                    status_code = 201
                    async def json(self):
                        return {"submission_id": "ext_ref_123"}
                return MockResponse()
            
            m.setattr("httpx.AsyncClient.post", mock_post)

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Step 1: Submit
                response = await client.post("/api/v1/lender-comparison/submit", json={
                    "application_id": app_id,
                    "lender_id": sample_lender.id,
                    "product_id": sample_products[0].id
                }, headers={"X-User-Id": "test_user_1"})
                
                assert response.status_code == 201
                data = response.json()
                assert data["status"] == "SUBMITTED"
                assert data["application_id"] == app_id
                
                # Step 2: Verify Database State (FINTRAC Compliance)
                # Check audit fields
                submissions = await db_session.execute(
                    f"SELECT * FROM submissions WHERE application_id = '{app_id}'"
                )
                # Using raw SQL or ORM depending on setup, assuming ORM here:
                from sqlalchemy import select
                stmt = select(Submission).where(Submission.application_id == app_id)
                result = await db_session.execute(stmt)
                sub_record = result.scalar_one_or_none()
                
                assert sub_record is not None
                assert sub_record.created_by == "test_user_1"
                assert sub_record.lender_id == sample_lender.id
                assert sub_record.submitted_at is not None

    async def test_get_submissions_history(self, app, db_session: AsyncSession, sample_lender):
        def override_get_db():
            yield db_session
        app.dependency_overrides[get_async_session] = override_get_db
        
        # Seed a submission
        sub = Submission(
            application_id=str(uuid4()),
            lender_id=sample_lender.id,
            status="PENDING",
            created_by="audit_user"
        )
        db_session.add(sub)
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Assuming a GET endpoint exists for history
            response = await client.get(f"/api/v1/lender-comparison/submissions/{sub.application_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
            # Verify PII minimization (ensure SIN not present in history if joined)
            # Note: Depends on schema implementation
            assert "sin" not in str(data) 

    async def test_submit_duplicate_handling(self, app, db_session: AsyncSession, sample_lender):
        def override_get_db():
            yield db_session
        app.dependency_overrides[get_async_session] = override_get_db
        
        app_id = str(uuid4())
        
        with pytest.MonkeyPatch().context() as m:
            async def mock_post(*args, **kwargs):
                class MockResponse:
                    status_code = 201
                    async def json(self):
                        return {"submission_id": "ref_1"}
                return MockResponse()
            m.setattr("httpx.AsyncClient.post", mock_post)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # First Submit
                r1 = await client.post("/api/v1/lender-comparison/submit", json={
                    "application_id": app_id,
                    "lender_id": sample_lender.id,
                    "product_id": 1
                }, headers={"X-User-Id": "user_1"})
                assert r1.status_code == 201

                # Second Submit (Should be allowed or rejected based on business logic)
                # Assuming idempotency or rejection
                r2 = await client.post("/api/v1/lender-comparison/submit", json={
                    "application_id": app_id,
                    "lender_id": sample_lender.id,
                    "product_id": 1
                }, headers={"X-User-Id": "user_1"})
                
                # If logic prevents duplicates:
                # assert r2.status_code == 400
                # If logic allows multiple submissions:
                assert r2.status_code == 201
```