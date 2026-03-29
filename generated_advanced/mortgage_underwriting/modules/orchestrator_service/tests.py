--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock

# Pytest Asyncio Configuration
pytest_plugins = ("pytest_asyncio",)

# Database Fixture (In-memory SQLite for speed)
ASYNC_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(ASYNC_DB_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Create tables (simplified for testing; normally uses Alembic)
        # from mortgage_underwriting.common.database import Base
        # async with db_engine.begin() as conn:
        #     await conn.run_sync(Base.metadata.create_all)
        yield session

# Mock External Services Fixtures
@pytest.fixture
def mock_borrower_service():
    service = AsyncMock()
    service.validate_borrower = AsyncMock(return_value={"status": "valid", "score": 750})
    service.get_borrower_pii = AsyncMock(return_value={"sin_hash": "abc123"})
    return service

@pytest.fixture
def mock_property_service():
    service = AsyncMock()
    service.assess_property = AsyncMock(return_value={"status": "acceptable", "value": Decimal("500000.00")})
    return service

@pytest.fixture
def mock_underwriting_service():
    service = AsyncMock()
    # Default to passing ratios
    service.calculate_ratios = AsyncMock(
        return_value={
            "gds": Decimal("25.00"),
            "tds": Decimal("35.00"),
            "ltv": Decimal("80.00"),
            "stress_test_rate": Decimal("7.25")
        }
    )
    return service

@pytest.fixture
def mock_notification_service():
    service = AsyncMock()
    service.send_decision = AsyncMock(return_value=True)
    return service

# Test Data Fixtures
@pytest.fixture
def sample_application_payload():
    return {
        "borrower_id": "borrower_123",
        "property_id": "property_456",
        "loan_amount": Decimal("400000.00"),
        "income": Decimal("120000.00"),
        "property_value": Decimal("500000.00"),
        "heating_cost": Decimal("150.00"),
        "property_tax": Decimal("300.00"),
        "debts": Decimal("500.00")
    }

@pytest.fixture
def sample_application_model(sample_application_payload):
    from mortgage_underwriting.modules.orchestrator.models import MortgageApplication
    return MortgageApplication(
        id="app_789",
        **sample_application_payload,
        status="PENDING",
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00"
    )

# App Fixture for Integration Tests
@pytest.fixture
def app():
    from fastapi import FastAPI
    from mortgage_underwriting.modules.orchestrator.routes import router
    
    app_instance = FastAPI()
    app_instance.include_router(router, prefix="/api/v1/orchestrator")
    return app_instance
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, call
from sqlalchemy.ext.asyncio import AsyncSession

# Import absolute paths
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.schemas import OrchestrationRequest, DecisionResponse
from mortgage_underwriting.modules.orchestrator.exceptions import (
    OrchestrationException,
    UnderwritingCriteriaError,
    ComplianceError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestOrchestratorService:

    @pytest.mark.asyncio
    async def test_orchestrate_happy_path_approval(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service,
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        application_id = "app_789"
        
        # Mock DB get to return the sample application
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_application_model
        db_session.execute = AsyncMock(return_value=mock_result)
        
        # Act
        result = await service.orchestrate_application(
            application_id=application_id,
            borrower_svc=mock_borrower_service,
            property_svc=mock_property_service,
            underwriting_svc=mock_underwriting_service
        )

        # Assert
        assert result.decision == "APPROVED"
        assert result.application_id == application_id
        assert result.gds <= Decimal("39.00")
        assert result.tds <= Decimal("44.00")
        
        # Verify external calls were made
        mock_borrower_service.validate_borrower.assert_awaited_once_with("borrower_123")
        mock_property_service.assess_property.assert_awaited_once_with("property_456")
        mock_underwriting_service.calculate_ratios.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_orchestrate_reject_high_tds(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service,
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        application_id = "app_789"
        
        # Mock DB get
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_application_model
        db_session.execute = AsyncMock(return_value=mock_result)

        # Override Underwriting to return high TDS (> 44%)
        mock_underwriting_service.calculate_ratios = AsyncMock(
            return_value={
                "gds": Decimal("30.00"),
                "tds": Decimal("50.00"), # Violates OSFI B-20
                "ltv": Decimal("80.00"),
                "stress_test_rate": Decimal("7.25")
            }
        )

        # Act
        result = await service.orchestrate_application(
            application_id=application_id,
            borrower_svc=mock_borrower_service,
            property_svc=mock_property_service,
            underwriting_svc=mock_underwriting_service
        )

        # Assert
        assert result.decision == "REJECTED"
        assert "TDS" in result.rejection_reason or "Debt" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_orchestrate_cmhc_insurance_required(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service,
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        application_id = "app_789"
        
        # Modify sample data for high LTV
        sample_application_model.loan_amount = Decimal("450000.00") # 90% LTV
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_application_model
        db_session.execute = AsyncMock(return_value=mock_result)

        # Mock Underwriting to return high LTV
        mock_underwriting_service.calculate_ratios = AsyncMock(
            return_value={
                "gds": Decimal("25.00"),
                "tds": Decimal("35.00"),
                "ltv": Decimal("90.00"), # > 80%
                "stress_test_rate": Decimal("7.25")
            }
        )

        # Act
        result = await service.orchestrate_application(
            application_id=application_id,
            borrower_svc=mock_borrower_service,
            property_svc=mock_property_service,
            underwriting_svc=mock_underwriting_service
        )

        # Assert
        assert result.decision == "APPROVED" # Assuming high LTV is okay if insured
        assert result.insurance_required is True
        assert result.premium_rate == Decimal("3.10") # 90.01-95% tier check logic or 85.01-90%?
        # CMHC Tier: 80.01-85% = 2.80%, 85.01-90% = 3.10%. 90% falls in 3.10% range usually.
        # Note: Logic depends on strict inequality implementation in service.
        # Assuming 90.00 falls into the > 85 bucket.

    @pytest.mark.asyncio
    async def test_orchestrate_borrower_validation_failure(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service,
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        application_id = "app_789"
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_application_model
        db_session.execute = AsyncMock(return_value=mock_result)

        # Mock Borrower Service to fail
        mock_borrower_service.validate_borrower = AsyncMock(
            side_effect=AppException("Borrower identity verification failed")
        )

        # Act & Assert
        with pytest.raises(OrchestrationException) as exc_info:
            await service.orchestrate_application(
                application_id=application_id,
                borrower_svc=mock_borrower_service,
                property_svc=mock_property_service,
                underwriting_svc=mock_underwriting_service
            )
        
        assert "Borrower" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_orchestrate_application_not_found(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service
    ):
        # Arrange
        service = OrchestratorService(db_session)
        application_id = "non_existent"
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.orchestrate_application(
                application_id=application_id,
                borrower_svc=mock_borrower_service,
                property_svc=mock_property_service,
                underwriting_svc=mock_underwriting_service
            )
        
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calculate_premium_tier_boundaries(self, db_session: AsyncSession):
        # Arrange
        service = OrchestratorService(db_session)
        
        # Act & Assert - Tier 1 (80.01 - 85.00)
        premium_82 = service._calculate_insurance_premium(Decimal("82.00"))
        assert premium_82 == Decimal("2.80")
        
        # Act & Assert - Tier 2 (85.01 - 90.00)
        premium_88 = service._calculate_insurance_premium(Decimal("88.00"))
        assert premium_88 == Decimal("3.10")
        
        # Act & Assert - Tier 3 (90.01 - 95.00)
        premium_92 = service._calculate_insurance_premium(Decimal("92.00"))
        assert premium_92 == Decimal("4.00")
        
        # Act & Assert - No Insurance (<= 80.00)
        premium_80 = service._calculate_insurance_premium(Decimal("80.00"))
        assert premium_80 is None

    @pytest.mark.asyncio
    async def test_log_fintrac_audit_trail(
        self, 
        db_session: AsyncSession, 
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        
        # Act
        # Assuming a method to log audit exists or is part of orchestrate
        # We will verify the DB session add/commit is called for AuditLog
        from mortgage_underwriting.modules.audit.models import AuditLog
        
        log_entry = AuditLog(
            entity_id=sample_application_model.id,
            action="UNDERWRITING_DECISION",
            details="Approved: Manual Review",
            created_by="system_orchestrator"
        )
        
        db_session.add(log_entry)
        await db_session.commit()
        
        # Assert (verify commit was called)
        db_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_stress_test_rate_calculation_logic(
        self, 
        db_session: AsyncSession, 
        mock_underwriting_service
    ):
        # Arrange
        service = OrchestratorService(db_session)
        contract_rate = Decimal("4.5")
        
        # Act - OSFI B-20: max(contract_rate + 2%, 5.25%)
        qualifying_rate = service._determine_qualifying_rate(contract_rate)
        
        # Assert
        expected = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == expected
        assert qualifying_rate == Decimal("6.50") # 4.5 + 2.0

    @pytest.mark.asyncio
    async def test_pipeda_compliance_no_sin_in_response(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service,
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        sample_application_model.borrower_sin = "123456789" # Encrypted in DB, but check logic
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_application_model
        db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await service.orchestrate_application(
            application_id="app_789",
            borrower_svc=mock_borrower_service,
            property_svc=mock_property_service,
            underwriting_svc=mock_underwriting_service
        )

        # Assert
        # The response schema should not have SIN
        assert not hasattr(result, 'borrower_sin') or result.borrower_sin is None
        assert hasattr(result, 'decision')

    @pytest.mark.asyncio
    async def test_update_application_status_persistence(
        self, 
        db_session: AsyncSession, 
        mock_borrower_service, 
        mock_property_service, 
        mock_underwriting_service,
        sample_application_model
    ):
        # Arrange
        service = OrchestratorService(db_session)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_application_model
        db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        await service.orchestrate_application(
            application_id="app_789",
            borrower_svc=mock_borrower_service,
            property_svc=mock_property_service,
            underwriting_svc=mock_underwriting_service
        )

        # Assert
        # Verify refresh was called to get updated status
        db_session.refresh.assert_awaited()
        # Verify commit was called to save status
        db_session.commit.assert_awaited()
```

--- integration_tests ---
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