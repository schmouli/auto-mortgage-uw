import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingEndpoints:

    async def test_create_message_endpoint_success(self, client: AsyncClient, sample_message_payload):
        response = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["content"] == sample_message_payload["content"]
        assert data["application_id"] == sample_message_payload["application_id"]
        assert "created_at" in data  # FINTRAC audit requirement

    async def test_create_message_endpoint_missing_content_fails(self, client: AsyncClient):
        invalid_payload = {
            "application_id": "app_1",
            "sender_id": "u1",
            "recipient_id": "u2"
            # missing content
        }
        response = await client.post("/api/v1/messaging-conditions/messages", json=invalid_payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_get_messages_by_application(self, client: AsyncClient, db_session, sample_message_payload):
        # Create two messages for the same app
        await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)
        sample_message_payload["content"] = "Second message"
        await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)

        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={sample_message_payload['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(msg["application_id"] == sample_message_payload["application_id"] for msg in data)

    async def test_get_messages_empty_list(self, client: AsyncClient):
        response = await client.get("/api/v1/messaging-conditions/messages?application_id=nonexistent")
        assert response.status_code == 200
        assert response.json() == []

@pytest.mark.integration
@pytest.mark.asyncio
class TestConditionEndpoints:

    async def test_create_condition_endpoint_success(self, client: AsyncClient, sample_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "PENDING"
        assert data["amount_required"] == "0.00" # Decimal serialized as string
        assert "created_at" in data

    async def test_create_condition_with_financial_amount(self, client: AsyncClient, sample_financial_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_financial_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        # Verify precision is maintained
        assert data["amount_required"] == "15000.00"

    async def test_update_condition_status_to_satisfied(self, client: AsyncClient, db_session, sample_condition_payload):
        # 1. Create a condition
        create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        cond_id = create_resp.json()["id"]

        # 2. Update status
        update_payload = {"status": "SATISFIED"}
        update_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["status"] == "SATISFIED"
        assert "updated_at" in data

    async def test_update_nonexistent_condition_returns_404(self, client: AsyncClient):
        update_payload = {"status": "SATISFIED"}
        response = await client.patch("/api/v1/messaging-conditions/conditions/99999", json=update_payload)
        
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_get_conditions_summary_endpoint(self, client: AsyncClient, sample_condition_payload):
        app_id = sample_condition_payload["application_id"]
        
        # Create a pending condition
        await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        
        # Create a satisfied condition
        sample_condition_payload["description"] = "Another one"
        satisfied_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        cond_id = satisfied_resp.json()["id"]
        await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json={"status": "SATISFIED"})

        # Get summary
        response = await client.get(f"/api/v1/messaging-conditions/conditions/summary?application_id={app_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["pending"] == 1
        assert data["satisfied"] == 1
        assert data["is_met"] is False

    async def test_get_conditions_by_application(self, client: AsyncClient, sample_condition_payload):
        app_id = sample_condition_payload["application_id"]
        await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)

        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={app_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["application_id"] == app_id

@pytest.mark.integration
@pytest.mark.asyncio
class TestRegulatoryCompliance:

    async def test_audit_fields_present_on_message_creation(self, client: AsyncClient, sample_message_payload):
        """FINTRAC: Verify audit trail exists immediately"""
        response = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)
        data = response.json()
        assert "created_at" in data
        # Assuming created_by is handled via auth context injection (omitted in simple test payload but checked in model)
        
    async def test_no_pii_leakage_in_error_response(self, client: AsyncClient):
        """PIPEDA: Ensure sensitive data isn't leaked in 422/500 errors"""
        # Sending a malformed payload that might contain PII in fields that don't exist
        malicious_payload = {
            "application_id": "app_1",
            "sender_id": "hacker",
            "content": "My SIN is 123-456-789", 
            "non_existent_field": "secret_data"
        }
        response = await client.post("/api/v1/messaging-conditions/messages", json=malicious_payload)
        
        # FastAPI default validation error hides the payload values, showing only field names
        assert response.status_code == 422
        detail = response.json().get("detail", [])
        # Ensure the SIN or content isn't echoed back in the error detail
        error_str = str(detail)
        assert "123-456-789" not in error_str
        assert "secret_data" not in error_str

    async def test_decimal_precision_preserved(self, client: AsyncClient, sample_financial_condition_payload):
        """General: Ensure no float precision loss for financial conditions"""
        # Using a high precision number
        sample_financial_condition_payload["amount_required"] = "123456.78"
        
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_financial_condition_payload)
        data = response.json()
        
        assert data["amount_required"] == "123456.78"