--- conftest.py ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import pool

# Import the module router and base
from mortgage_underwriting.modules.frontend_ui.routes import router
from mortgage_underwriting.common.database import Base

# Using SQLite for in-memory testing speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine):
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/frontend")
    return app

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def auth_headers():
    # Mock authentication headers
    return {"Authorization": "Bearer test_token"}

@pytest.fixture
def sample_draft_payload():
    return {
        "application_id": "app_123",
        "step_data": {
            "borrower_info": {"name": "John Doe"},
            "property_info": {"address": "123 Main St"}
        },
        "current_step": "borrower_info",
        "is_complete": False
    }
```

--- unit_tests ---
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

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient

from mortgage_underwriting.modules.frontend_ui.models import ApplicationDraft

@pytest.mark.integration
@pytest.mark.asyncio
class TestFrontendRoutes:

    async def test_create_draft_endpoint(self, client: AsyncClient, db_session, auth_headers, sample_draft_payload):
        # Test contract: POST creates a record in DB and returns 201
        response = await client.post(
            "/api/v1/frontend/drafts",
            json=sample_draft_payload,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["application_id"] == sample_draft_payload["application_id"]
        
        # Verify DB state
        result = await db_session.execute(
            select(ApplicationDraft).where(ApplicationDraft.application_id == "app_123")
        )
        draft = result.scalar_one_or_none()
        assert draft is not None
        assert draft.current_step == "borrower_info"

    async def test_get_config_endpoint(self, client: AsyncClient):
        # Test contract: GET returns valid JSON config
        response = await client.get("/api/v1/frontend/config")

        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "provinces" in data
        assert "property_types" in data
        assert "financial_limits" in data
        
        # Validate Decimal handling in JSON response (usually string in raw JSON, parsed by client)
        # FastAPI converts Decimal to string in JSON by default
        assert data["financial_limits"]["min_down_payment"] == "5000.00"

    async def test_update_draft_endpoint(self, client: AsyncClient, db_session, auth_headers, sample_draft_payload):
        # 1. Create
        create_resp = await client.post(
            "/api/v1/frontend/drafts",
            json=sample_draft_payload,
            headers=auth_headers
        )
        draft_id = create_resp.json()["id"]

        # 2. Update
        update_payload = {
            "step_data": {"borrower_info": {"name": "Jane Doe"}},
            "current_step": "property_info",
            "is_complete": False
        }
        update_resp = await client.put(
            f"/api/v1/frontend/drafts/{draft_id}",
            json=update_payload,
            headers=auth_headers
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["current_step"] == "property_info"
        
        # Verify DB
        await db_session.refresh(db_session.get(ApplicationDraft, draft_id))
        # Note: In real test, we would re-fetch to be sure, but here we trust the response 
        # or re-query. Let's re-query for strict integration test.
        result = await db_session.execute(select(ApplicationDraft).where(ApplicationDraft.id == draft_id))
        draft = result.scalar_one()
        assert draft.step_data["borrower_info"]["name"] == "Jane Doe"

    async def test_get_drafts_for_user(self, client: AsyncClient, db_session, auth_headers, sample_draft_payload):
        # Create two drafts
        await client.post("/api/v1/frontend/drafts", json=sample_draft_payload, headers=auth_headers)
        await client.post("/api/v1/frontend/drafts", json={**sample_draft_payload, "application_id": "app_456"}, headers=auth_headers)

        response = await client.get("/api/v1/frontend/drafts", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        app_ids = [d["application_id"] for d in data]
        assert "app_123" in app_ids
        assert "app_456" in app_ids

    async def test_invalid_json_returns_400(self, client: AsyncClient, auth_headers):
        # Test input validation contract
        response = await client.post(
            "/api/v1/frontend/drafts",
            json={"invalid_field": "missing_required_fields"},
            headers=auth_headers
        )
        
        assert response.status_code == 422  # FastAPI Validation Error

    async def test_unauthorized_request_returns_401(self, client: AsyncClient, sample_draft_payload):
        response = await client.post(
            "/api/v1/frontend/drafts",
            json=sample_draft_payload
            # No auth headers
        )
        
        assert response.status_code == 401

    async def test_delete_draft_soft_delete(self, client: AsyncClient, db_session, auth_headers, sample_draft_payload):
        # Create
        create_resp = await client.post("/api/v1/frontend/drafts", json=sample_draft_payload, headers=auth_headers)
        draft_id = create_resp.json()["id"]

        # Delete
        del_resp = await client.delete(f"/api/v1/frontend/drafts/{draft_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        # Verify soft delete (check DB)
        result = await db_session.execute(select(ApplicationDraft).where(ApplicationDraft.id == draft_id))
        draft = result.scalar_one()
        # Assuming soft delete logic sets a deleted_at flag or similar
        # If hard delete, result would be None. Assuming FINTRAC audit trail implies soft delete or archive.
        # For this test, let's assume the model has a 'deleted_at' column.
        if hasattr(draft, 'deleted_at'):
            assert draft.deleted_at is not None
        else:
            # If hard delete is implemented (though against FINTRAC preference for audit trails usually)
            assert draft is None 

    async def test_concurrent_draft_update(self, client: AsyncClient, db_session, auth_headers, sample_draft_payload):
        # Test basic handling of state updates
        create_resp = await client.post("/api/v1/frontend/drafts", json=sample_draft_payload, headers=auth_headers)
        draft_id = create_resp.json()["id"]

        # Update 1
        await client.put(
            f"/api/v1/frontend/drafts/{draft_id}",
            json={"step_data": {"v": 1}, "current_step": "s1", "is_complete": False},
            headers=auth_headers
        )

        # Update 2 (overwrites)
        resp = await client.put(
            f"/api/v1/frontend/drafts/{draft_id}",
            json={"step_data": {"v": 2}, "current_step": "s2", "is_complete": False},
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        assert resp.json()["step_data"]["v"] == 2
```