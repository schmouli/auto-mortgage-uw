```python
import pytest
from decimal import Decimal

@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingConditionsAPI:

    async def test_create_condition_endpoint(self, client, valid_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=valid_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["application_id"] == 101
        assert data["status"] == "PENDING"
        assert "created_at" in data

    async def test_create_monetary_condition_endpoint(self, client, monetary_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=monetary_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        # Ensure Decimal is serialized correctly (string in JSON)
        assert data["required_amount"] == "50000.00"

    async def test_create_condition_invalid_payload(self, client):
        # Missing required fields
        response = await client.post("/api/v1/messaging-conditions/conditions", json={"application_id": 1})
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_conditions_for_application(self, client, valid_condition_payload):
        # Create two conditions
        await client.post("/api/v1/messaging-conditions/conditions", json=valid_condition_payload)
        payload_2 = {**valid_condition_payload, "description": "Second Condition"}
        await client.post("/api/v1/messaging-conditions/conditions", json=payload_2)
        
        # Retrieve
        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={valid_condition_payload['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_update_condition_status(self, client, seeded_condition):
        # seeded_condition comes from conftest with ID
        response = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{seeded_condition.id}",
            json={"status": "MET"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "MET"
        assert data["id"] == seeded_condition.id

    async def test_update_condition_invalid_status(self, client, seeded_condition):
        response = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{seeded_condition.id}",
            json={"status": "INVALID_STATUS"}
        )
        
        assert response.status_code == 422

    async def test_update_nonexistent_condition(self, client):
        response = await client.patch(
            "/api/v1/messaging-conditions/conditions/99999",
            json={"status": "MET"}
        )
        
        assert response.status_code == 404

    async def test_send_message_endpoint(self, client, valid_message_payload):
        response = await client.post("/api/v1/messaging-conditions/messages", json=valid_message_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["subject"] == "Underwriting Condition Added"

    async def test_send_message_missing_recipient(self, client):
        payload = {
            "application_id": 1,
            "subject": "Hello",
            "body": "World"
            # Missing recipient
        }
        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        assert response.status_code == 422

    async def test_get_messages_for_application(self, client, valid_message_payload):
        await client.post("/api/v1/messaging-conditions/messages", json=valid_message_payload)
        
        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={valid_message_payload['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["application_id"] == valid_message_payload['application_id']

    async def test_full_workflow_condition_to_message(self, client, valid_condition_payload, valid_message_payload):
        # 1. Create Condition
        cond_resp = await client.post("/api/v1/messaging-conditions/conditions", json=valid_condition_payload)
        assert cond_resp.status_code == 201
        cond_id = cond_resp.json()["id"]
        
        # 2. Send Message about the condition
        msg_payload = {
            **valid_message_payload,
            "body": f"Please address condition #{cond_id}"
        }
        msg_resp = await client.post("/api/v1/messaging-conditions/messages", json=msg_payload)
        assert msg_resp.status_code == 201
        
        # 3. Mark condition as Met
        patch_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json={"status": "MET"})
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "MET"
        
        # 4. Verify history (audit fields)
        get_cond_resp = await client.get(f"/api/v1/messaging-conditions/conditions/{cond_id}")
        cond_data = get_cond_resp.json()
        assert cond_data["created_at"] is not None
        assert cond_data["updated_at"] is not None
```