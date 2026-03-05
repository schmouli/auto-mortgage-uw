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