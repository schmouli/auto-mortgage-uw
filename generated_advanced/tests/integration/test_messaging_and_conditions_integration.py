import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal
from datetime import datetime, timedelta

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatusEnum, MessageCategoryEnum

@pytest.mark.integration
class TestConditionsAPI:
    
    @pytest.mark.asyncio
    async def test_create_condition_endpoint(self, client: AsyncClient, db_session, sample_application_id):
        """Test creating a condition via API."""
        # Mock the email gateway dependency in the app if necessary, 
        # but for conditions, it might not trigger an email immediately.
        # Here we test the endpoint persistence.
        
        payload = {
            "application_id": sample_application_id,
            "description": "Employment verification letter required.",
            "required_by_date": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }

        response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] == ConditionStatusEnum.PENDING.value
        assert data["description"] == payload["description"]
        
        # Verify DB Persistence
        stmt = select(Condition).where(Condition.application_id == sample_application_id)
        result = await db_session.execute(stmt)
        db_condition = result.scalar_one_or_none()
        assert db_condition is not None
        assert db_condition.description == payload["description"]

    @pytest.mark.asyncio
    async def test_list_conditions_by_application(self, client: AsyncClient, db_session, sample_application_id):
        """Test retrieving all conditions for a specific application."""
        # Seed data
        cond1 = Condition(
            application_id=sample_application_id,
            description="Condition 1",
            status=ConditionStatusEnum.PENDING
        )
        cond2 = Condition(
            application_id=sample_application_id,
            description="Condition 2",
            status=ConditionStatusEnum.MET
        )
        db_session.add(cond1)
        db_session.add(cond2)
        await db_session.commit()

        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_application_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        descriptions = [c["description"] for c in data]
        assert "Condition 1" in descriptions
        assert "Condition 2" in descriptions

    @pytest.mark.asyncio
    async def test_update_condition_status(self, client: AsyncClient, db_session, sample_application_id):
        """Test updating a condition status (e.g., fulfilling it)."""
        # Seed data
        cond = Condition(
            application_id=sample_application_id,
            description="Initial Condition",
            status=ConditionStatusEnum.PENDING
        )
        db_session.add(cond)
        await db_session.commit()
        await db_session.refresh(cond)

        update_payload = {
            "status": ConditionStatusEnum.MET.value,
            "notes": "Document uploaded to portal."
        }

        response = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond.id}", json=update_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ConditionStatusEnum.MET.value
        assert data["notes"] == update_payload["notes"]
        
        # Verify DB Update
        await db_session.refresh(cond)
        assert cond.status == ConditionStatusEnum.MET
        assert cond.notes == update_payload["notes"]
        assert cond.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_condition_invalid_transition(self, client: AsyncClient, db_session, sample_application_id):
        """Test that invalid status transitions are rejected (if business logic enforces this)."""
        cond = Condition(
            application_id=sample_application_id,
            description="Completed",
            status=ConditionStatusEnum.MET
        )
        db_session.add(cond)
        await db_session.commit()
        await db_session.refresh(cond)

        # Attempt to revert MET to PENDING (assuming this is invalid logic)
        update_payload = {"status": ConditionStatusEnum.PENDING.value}
        
        response = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond.id}", json=update_payload)
        
        # Expecting 422 or 400 depending on implementation detail
        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestMessagingAPI:
    
    @pytest.mark.asyncio
    async def test_send_message_endpoint(self, client: AsyncClient, db_session, sample_application_id):
        """Test sending a message via API."""
        payload = {
            "application_id": sample_application_id,
            "recipient_email": "user@example.com",
            "subject": "Application Update",
            "content": "Your application is under review.",
            "category": MessageCategoryEnum.GENERAL.value
        }

        # We expect 201, but the actual email sending might be mocked in the app setup 
        # or handled via background task. We check the DB record.
        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] in ["SENT", "QUEUED"] # Depending on sync/async implementation
        
        # Verify DB
        stmt = select(Message).where(Message.application_id == sample_application_id)
        result = await db_session.execute(stmt)
        db_msg = result.scalar_one_or_none()
        assert db_msg is not None
        assert db_msg.subject == "Application Update"
        # PIPEDA Check: Ensure content is not returned in list view (if implemented), 
        # but here we get detail view so it's okay for internal system.

    @pytest.mark.asyncio
    async def test_get_messages_by_application(self, client: AsyncClient, db_session, sample_application_id):
        """Test retrieving message history."""
        msg = Message(
            application_id=sample_application_id,
            recipient_email="test@example.com",
            subject="Subject 1",
            content="Body 1",
            status="SENT"
        )
        db_session.add(msg)
        await db_session.commit()

        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={sample_application_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["subject"] == "Subject 1"
        # Ensure PII is not leaked in logs (implicit check by not crashing)

    @pytest.mark.asyncio
    async def test_message_validation_missing_fields(self, client: AsyncClient):
        """Test validation error on missing required fields."""
        payload = {
            "recipient_email": "user@example.com",
            # Missing application_id, subject, content
        }

        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity
        errors = response.json()["detail"]
        error_fields = [e["loc"][1] for e in errors]
        assert "application_id" in error_fields
        assert "subject" in error fields

    @pytest.mark.asyncio
    async def test_condition_workflow_integration(self, client: AsyncClient, db_session, sample_application_id):
        """Test a workflow: Create condition -> Send Message -> Fulfill Condition."""
        
        # 1. Create Condition
        cond_payload = {
            "application_id": sample_application_id,
            "description": "Upload ID",
            "required_by_date": (datetime.utcnow() + timedelta(days=5)).isoformat()
        }
        cond_resp = await client.post("/api/v1/messaging-conditions/conditions", json=cond_payload)
        assert cond_resp.status_code == 201
        cond_id = cond_resp.json()["id"]

        # 2. Send Message about Condition
        msg_payload = {
            "application_id": sample_application_id,
            "recipient_email": "borrower@example.com",
            "subject": "Action Required: Upload ID",
            "content": f"Please fulfill condition ID {cond_id}",
            "category": MessageCategoryEnum.DOCUMENT_REQUEST.value
        }
        msg_resp = await client.post("/api/v1/messaging-conditions/messages", json=msg_payload)
        assert msg_resp.status_code == 201

        # 3. Fulfill Condition
        update_resp = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{cond_id}", 
            json={"status": ConditionStatusEnum.MET.value}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == ConditionStatusEnum.MET.value

        # 4. Verify Final State
        final_cond_resp = await client.get(f"/api/v1/messaging-conditions/conditions/{cond_id}")
        assert final_cond_resp.json()["status"] == ConditionStatusEnum.MET.value