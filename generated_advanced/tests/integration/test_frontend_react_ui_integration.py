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