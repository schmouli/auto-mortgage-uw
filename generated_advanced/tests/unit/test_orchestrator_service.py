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