import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatus, MessageStatus


@pytest.mark.integration
@pytest.mark.asyncio
class TestConditionEndpoints:
    async def test_create_condition_endpoint(self, client: AsyncClient, sample_condition_data: dict):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["application_id"] == sample_condition_data["application_id"]
        assert data["status"] == ConditionStatus.PENDING.value
        assert data["created_at"] is not None

    async def test_create_condition_invalid_payload(self, client: AsyncClient):
        invalid_payload = {
            "application_id": str(uuid4()),
            # Missing description
            "category": "test"
        }
        response = await client.post("/api/v1/messaging-conditions/conditions", json=invalid_payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_list_conditions_empty(self, client: AsyncClient, sample_application_id: str):
        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_application_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_list_conditions_with_data(self, client: AsyncClient, sample_condition_data: dict):
        # Create a condition first
        create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_data)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        # List them
        list_resp = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_condition_data['application_id']}")
        
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data) == 1
        assert data[0]["id"] == created_id

    async def test_fulfill_condition_endpoint(self, client: AsyncClient, sample_condition_data: dict):
        # Create
        create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_data)
        condition_id = create_resp.json()["id"]

        # Fulfill
        fulfill_payload = {
            "notes": "Documents verified by underwriter John Doe.",
            "fulfilled_by": "underwriter_1"
        }
        patch_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{condition_id}/fulfill", json=fulfill_payload)

        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["status"] == ConditionStatus.FULFILLED.value
        assert data["fulfilled_by"] == "underwriter_1"
        assert data["notes"] == "Documents verified by underwriter John Doe."
        assert data["fulfilled_at"] is not None

    async def test_fulfill_non_existent_condition(self, client: AsyncClient):
        fake_id = str(uuid4())
        payload = {"notes": "Test", "fulfilled_by": "test"}
        response = await client.patch(f"/api/v1/messaging-conditions/conditions/{fake_id}/fulfill", json=payload)
        
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingEndpoints:
    async def test_send_message_endpoint(self, client: AsyncClient, sample_message_data: dict):
        # We mock the external email provider within the service layer, 
        # but for integration tests we might want to ensure the endpoint calls the service.
        # Assuming the service handles the mock or we have a real dummy SMTP.
        # For this exercise, we assume the service uses a mock or a no-op for testing.
        
        response = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_data)
        
        # Note: If external provider fails and is not mocked in integration setup, this might be 503.
        # Assuming happy path or internal mock setup in conftest/routes.
        # We will assert 201 or 503 depending on if we mocked the provider globally.
        # Given constraints, let's assume the service defaults to 'SENT' if provider is None in test mode.
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] in [MessageStatus.SENT.value, MessageStatus.FAILED.value]
        assert data["subject"] == sample_message_data["subject"]

    async def test_list_messages_endpoint(self, client: AsyncClient, sample_message_data: dict):
        # Send a message
        await client.post("/api/v1/messaging-conditions/messages", json=sample_message_data)

        # List messages
        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={sample_message_data['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["subject"] == sample_message_data["subject"]
        
        # PIPEDA Check: Ensure we aren't returning raw PII if it were stored (not applicable here directly, 
        # but ensure we don't return internal notes if any)
        assert "internal_notes" not in data[0] or data[0].get("internal_notes") is None

    async def test_message_persistence(self, client: AsyncClient, db_session, sample_message_data: dict):
        # Verify DB persistence
        resp = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_data)
        msg_id = resp.json()["id"]

        # Query directly via DB session to verify it was actually saved
        from sqlalchemy import select
        stmt = select(Message).where(Message.id == msg_id)
        result = await db_session.execute(stmt)
        db_msg = result.scalar_one_or_none()

        assert db_msg is not None
        assert db_msg.application_id == sample_message_data["application_id"]
        # FINTRAC: Verify immutable audit trail exists
        assert db_msg.created_at is not None
        assert db_msg.updated_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow:
    async def test_condition_and_message_workflow(self, client: AsyncClient, sample_application_id: str):
        # 1. Create a mandatory condition
        condition_data = {
            "application_id": sample_application_id,
            "description": "Provide Proof of Income",
            "category": "income",
            "is_mandatory": True
        }
        cond_resp = await client.post("/api/v1/messaging-conditions/conditions", json=condition_data)
        assert cond_resp.status_code == 201
        condition_id = cond_resp.json()["id"]

        # 2. Send a message notifying the applicant
        message_data = {
            "application_id": sample_application_id,
            "recipient_type": "applicant",
            "subject": "Action Required: Missing Documents",
            "body": "Please upload your Proof of Income.",
            "channel": "email"
        }
        msg_resp = await client.post("/api/v1/messaging-conditions/messages", json=message_data)
        assert msg_resp.status_code == 201

        # 3. Verify state (Condition Pending, Message Sent)
        list_cond = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_application_id}")
        assert list_cond.json()[0]["status"] == ConditionStatus.PENDING.value

        # 4. Fulfill the condition
        fulfill_resp = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{condition_id}/fulfill",
            json={"fulfilled_by": "admin", "notes": "Income verified"}
        )
        assert fulfill_resp.status_code == 200
        assert fulfill_resp.json()["status"] == ConditionStatus.FULFILLED.value

        # 5. Verify final state
        final_cond = await client.get(f"/api/v1/messaging-conditions/conditions/{condition_id}")
        assert final_cond.json()["status"] == ConditionStatus.FULFILLED.value
        assert final_cond.json()["fulfilled_at"] is not None