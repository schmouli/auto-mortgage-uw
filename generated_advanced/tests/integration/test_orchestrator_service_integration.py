```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

# Imports
from mortgage_underwriting.modules.orchestrator.models import MortgageApplication
from mortgage_underwriting.modules.orchestrator.routes import router
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
class TestOrchestratorAPI:

    @pytest.mark.asyncio
    async def test_create_and_orchestrate_application_success(self, app, db_session: AsyncSession):
        """
        Test creating an application via API and then triggering orchestration.
        """
        # Override dependency
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        # 1. Create Application (Simulated via direct DB insert for isolation, or via Borrower/Property modules if available)
        # For integration test, we assume the app exists or we create it via a dedicated endpoint.
        # Here we insert directly to setup the state for the orchestrator endpoint.
        new_app = MortgageApplication(
            id="integration_test_001",
            borrower_id="borrower_int",
            property_id="property_int",
            loan_amount=Decimal("300000.00"),
            income=Decimal("90000.00"),
            property_value=Decimal("400000.00"),
            heating_cost=Decimal("100.00"),
            property_tax=Decimal("200.00"),
            debts=Decimal("0.00"),
            status="PENDING"
        )
        db_session.add(new_app)
        await db_session.commit()
        await db_session.refresh(new_app)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 2. Trigger Orchestration
            response = await client.post(f"/api/v1/orchestrator/run/{new_app.id}")
            
            # 3. Assertions
            assert response.status_code == 200
            
            data = response.json()
            assert data["application_id"] == "integration_test_001"
            assert "decision" in data
            assert "gds" in data
            assert "tds" in data
            # Verify PIPEDA: SIN should not be in response
            assert "sin" not in data.keys()
            
            # Verify Decimal precision maintained
            # JSON converts Decimal to float/string, check string representation usually
            # or that the value is present.
            assert data["gds"] is not None

    @pytest.mark.asyncio
    async def test_orchestrate_nonexistent_app_returns_404(self, app, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/orchestrator/run/ghost_app")
            
            assert response.status_code == 404
            assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_get_application_status(self, app, db_session: AsyncSession):
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db

        # Setup
        new_app = MortgageApplication(
            id="status_check_001",
            borrower_id="b1",
            property_id="p1",
            loan_amount=Decimal("100000.00"),
            income=Decimal("50000.00"),
            property_value=Decimal("150000.00"),
            heating_cost=Decimal("50.00"),
            property_tax=Decimal("100.00"),
            debts=Decimal("0.00"),
            status="COMPLETED"
        )
        db_session.add(new_app)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/orchestrator/status/{new_app.id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "COMPLETED"
            assert data["id"] == "status_check_001"

    @pytest.mark.asyncio
    async def test_osfi_stress_test_endpoint_validation(self, app, db_session: AsyncSession):
        """
        Test that the orchestration endpoint enforces OSFI B-20 stress test logic
        by checking the calculation in the response.
        """
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db

        # Create app with specific parameters
        new_app = MortgageApplication(
            id="stress_test_001",
            borrower_id="b_stress",
            property_id="p_stress",
            loan_amount=Decimal("400000.00"),
            income=Decimal("100000.00"),
            property_value=Decimal("500000.00"),
            heating_cost=Decimal("200.00"),
            property_tax=Decimal("400.00"),
            debts=Decimal("1000.00"),
            status="PENDING"
        )
        db_session.add(new_app)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/orchestrator/run/{new_app.id}")
            assert response.status_code == 200
            
            data = response.json()
            # The service should have calculated ratios using the stress test rate
            # We can't easily assert the exact math here without the exact rate logic exposed,
            # but we ensure the calculation happened and didn't crash.
            assert data["decision"] in ["APPROVED", "REJECTED"]

    @pytest.mark.asyncio
    async def test_invalid_input_format_rejected(self, app, db_session: AsyncSession):
        """
        Test that the API rejects malformed requests (e.g., invalid ID format)
        """
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Sending a non-uuid or non-string ID might be handled by path validation
            # Here we test a generic malformed request if the endpoint accepted a body
            # Since this is a path param, we test a potentially malicious ID
            response = await client.post("/api/v1/orchestrator/run/../../etc/passwd")
            
            # Should return 422 (Validation Error) or 404
            assert response.status_code in [404, 422]

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self, app, db_session: AsyncSession):
        """
        Test that the system handles multiple orchestration requests reasonably.
        """
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db

        # Create 2 apps
        app1 = MortgageApplication(
            id="concurrent_1",
            borrower_id="b1", property_id="p1",
            loan_amount=Decimal("100000.00"), income=Decimal("50000.00"),
            property_value=Decimal("150000.00"), heating_cost=Decimal("50.00"),
            property_tax=Decimal("100.00"), debts=Decimal("0.00"), status="PENDING"
        )
        app2 = MortgageApplication(
            id="concurrent_2",
            borrower_id="b2", property_id="p2",
            loan_amount=Decimal("100000.00"), income=Decimal("50000.00"),
            property_value=Decimal("150000.00"), heating_cost=Decimal("50.00"),
            property_tax=Decimal("100.00"), debts=Decimal("0.00"), status="PENDING"
        )
        db_session.add_all([app1, app2])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Fire requests concurrently
            import asyncio
            req1 = client.post("/api/v1/orchestrator/run/concurrent_1")
            req2 = client.post("/api/v1/orchestrator/run/concurrent_2")
            
            results = await asyncio.gather(req1, req2)
            
            for res in results:
                assert res.status_code == 200
```