```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.frontend_ui.services import FrontendService
from mortgage_underwriting.modules.frontend_ui.schemas import DraftCreate, DraftResponse
from mortgage_underwriting.modules.frontend_ui.exceptions import DraftSaveError, InvalidStepError

@pytest.mark.unit
class TestFrontendService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def valid_draft_data(self):
        return DraftCreate(
            application_id="app_001",
            step_data={"income": 50000},
            current_step="income",
            is_complete=False
        )

    @pytest.mark.asyncio
    async def test_save_draft_success(self, mock_db, valid_draft_data):
        service = FrontendService(mock_db)
        
        # Mock the result of refresh to set an ID
        mock_draft_model = MagicMock()
        mock_draft_model.id = 1
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)

        result = await service.save_draft(valid_draft_data, user_id="user_123")

        assert result.application_id == "app_001"
        assert result.id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_draft_db_failure_raises_exception(self, mock_db, valid_draft_data):
        service = FrontendService(mock_db)
        mock_db.commit.side_effect = SQLAlchemyError("DB connection failed")

        with pytest.raises(DraftSaveError) as exc_info:
            await service.save_draft(valid_draft_data, user_id="user_123")
        
        assert "Failed to save draft" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_form_config_returns_decimals(self):
        # Ensure financial config returns Decimals, not floats
        service = FrontendService(AsyncMock()) # DB not needed for static config
        
        config = await service.get_form_config()

        assert "min_down_payment" in config
        assert isinstance(config["min_down_payment"], Decimal)
        assert config["min_down_payment"] == Decimal("5000.00")
        
        assert "max_amortization_years" in config
        assert isinstance(config["max_amortization_years"], int)

    @pytest.mark.asyncio
    async def test_validate_step_valid(self):
        service = FrontendService(AsyncMock())
        # Should not raise
        await service.validate_step("borrower_info")

    @pytest.mark.asyncio
    async def test_validate_step_invalid_raises(self):
        service = FrontendService(AsyncMock())
        with pytest.raises(InvalidStepError):
            await service.validate_step("non_existent_step")

    @pytest.mark.asyncio
    async def test_update_draft_overwrites_data(self, mock_db):
        service = FrontendService(mock_db)
        
        # Mock finding existing draft
        existing_draft = MagicMock()
        existing_draft.step_data = {"old": "data"}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_draft
        mock_db.execute.return_value = mock_result

        update_data = DraftCreate(
            application_id="app_001",
            step_data={"new": "data"},
            current_step="review",
            is_complete=True
        )

        await service.update_draft("app_001", update_data, user_id="user_123")

        assert existing_draft.step_data == {"new": "data"}
        assert existing_draft.current_step == "review"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pii_not_logged_in_service(self, mock_db, valid_draft_data, caplog):
        # Ensure PII in step_data is not explicitly logged
        service = FrontendService(mock_db)
        
        # Patch logger to capture output
        with patch("mortgage_underwriting.modules.frontend_ui.services.logger") as mock_logger:
            await service.save_draft(valid_draft_data, user_id="user_123")
            
            # Check that info was called, but verify args don't contain raw PII
            # (Assuming step_data might contain PII, we ensure we don't log the whole dict)
            for call in mock_logger.info.call_args_list:
                args, kwargs = call
                # Convert args to string to check content
                arg_str = str(args)
                assert "income" not in arg_str # Example field from fixture

```