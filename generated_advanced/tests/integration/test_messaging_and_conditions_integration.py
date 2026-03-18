import pytest
from httpx import AsyncClient
from sqlalchemy import select
from uuid import uuid4

from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition, ConditionStatus


@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingEndpoints:

    async def test_create_message_endpoint_success(self, client: AsyncClient, db_session: AsyncSession):
        payload = {
            "application_id": str(uuid4()),
            "recipient_type": "broker",
            "recipient_address": "broker@test.com",
            "channel": "email",
            "subject": "New Condition Added",
            "body": "Please review the requirements."
        }

        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["subject"] == payload["subject"]
        assert data["status"] == "sent" # Assuming default sent status for integration
        
        # Verify DB persistence
        stmt = select(Message).where(Message.id == data["id"])
        result = await db_session.execute(stmt)
        db_msg = result.scalar_one_or_none()
        assert db_msg is not None
        assert db_msg.recipient_address == "broker@test.com"

    async def test_create_message_invalid_channel(self, client: AsyncClient):
        payload = {
            "application_id": str(uuid4()),
            "recipient_type": "borrower",
            "recipient_address": "555-0199",
            "channel": "fax", # Invalid channel
            "subject": "Test",
            "body": "Test"
        }

        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        assert response.status_code == 422

    async def test_get_messages_by_application(self, client: AsyncClient, db_session: AsyncSession):
        app_id = str(uuid4())
        
        # Seed data directly
        msg1 = Message(
            application_id=app_id,
            recipient_type="borrower",
            recipient_address="user@test.com",
            channel="email",
            subject="Msg 1",
            body="Body 1",
            status="sent"
        )
        db_session.add(msg1)
        await db_session.commit()

        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={app_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["subject"] == "Msg 1"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConditionEndpoints:

    async def test_create_condition_workflow(self, client: AsyncClient, db_session: AsyncSession):
        """
        Multi-step workflow: Create condition -> Retrieve it -> Update it.
        """
        app_id = str(uuid4())
        
        # Step 1: Create Condition
        create_payload = {
            "application_id": app_id,
            "description": "Proof of down payment",
            "category": "assets",
            "due_days": 7
        }
        
        response = await client.post("/api/v1/messaging-conditions/conditions", json=create_payload)
        assert response.status_code == 201
        cond_data = response.json()
        condition_id = cond_data["id"]
        
        assert cond_data["status"] == ConditionStatus.PENDING
        
        # Step 2: Verify in DB
        stmt = select(Condition).where(Condition.id == condition_id)
        result = await db_session.execute(stmt)
        db_cond = result.scalar_one_or_none()
        assert db_cond is not None
        assert db_cond.due_days == 7

        # Step 3: Update Condition (Fulfill)
        update_payload = {
            "status": ConditionStatus.MET,
            "notes": "Bank statement received and verified."
        }
        
        response = await client.put(f"/api/v1/messaging-conditions/conditions/{condition_id}", json=update_payload)
        assert response.status_code == 200
        updated_data = response.json()
        
        assert updated_data["status"] == ConditionStatus.MET
        assert updated_data["notes"] == "Bank statement received and verified."
        
        # Step 4: Verify DB Update
        await db_session.refresh(db_cond)
        assert db_cond.status == ConditionStatus.MET
        assert db_cond.met_at is not None # Audit field check

    async def test_create_condition_validation_error(self, client: AsyncClient):
        payload = {
            "application_id": str(uuid4()),
            "description": "", # Invalid
            "category": "generic"
        }
        
        response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
        assert response.status_code == 422

    async def test_get_conditions_filter_by_status(self, client: AsyncClient, db_session: AsyncSession):
        app_id = str(uuid4())
        
        # Create pending condition
        cond1 = Condition(application_id=app_id, description="Pending 1", category="gen", status=ConditionStatus.PENDING)
        # Create met condition
        cond2 = Condition(application_id=app_id, description="Met 1", category="gen", status=ConditionStatus.MET)
        
        db_session.add_all([cond1, cond2])
        await db_session.commit()
        
        # Filter for pending
        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={app_id}&status=pending")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["description"] == "Pending 1"

    async def test_update_non_existent_condition(self, client: AsyncClient):
        fake_id = str(uuid4())
        payload = {"status": ConditionStatus.MET}
        
        response = await client.put(f"/api/v1/messaging-conditions/conditions/{fake_id}", json=payload)
        assert response.status_code == 404