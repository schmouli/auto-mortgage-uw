import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatus

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_condition_endpoint(client: AsyncClient):
    # Arrange
    payload = {
        "application_id": "app_integration_01",
        "description": "Employment Letter Required",
        "condition_type": "DocumentRequest",
        "due_date": "2024-12-31",
        "assigned_to": "underwriter_A"
    }
    
    # Act
    response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
    
    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["application_id"] == "app_integration_01"
    assert data["status"] == "Pending"
    assert "created_at" in data

@pytest.mark.asyncio
async def test_get_conditions_endpoint(client: AsyncClient, db_session: AsyncSession):
    # Arrange - Create a condition directly in DB
    new_cond = Condition(
        application_id="app_integration_02",
        description="Bank Statements",
        status=ConditionStatus.PENDING,
        created_by="test_runner"
    )
    db_session.add(new_cond)
    await db_session.commit()
    await db_session.refresh(new_cond)
    
    # Act
    response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id=app_integration_02")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["description"] == "Bank Statements"

@pytest.mark.asyncio
async def test_update_condition_workflow(client: AsyncClient, db_session: AsyncSession):
    # Arrange - Create condition
    create_payload = {
        "application_id": "app_workflow_01",
        "description": "Proof of Income",
        "condition_type": "DocumentRequest",
        "assigned_to": "underwriter_B"
    }
    create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=create_payload)
    cond_id = create_resp.json()["id"]
    
    # Act - Update condition to Met
    update_payload = {
        "status": "Met",
        "notes": "Verified via Paystub"
    }
    update_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json=update_payload)
    
    # Assert
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["status"] == "Met"
    assert updated_data["notes"] == "Verified via Paystub"
    
    # Verify in DB
    db_result = await db_session.get(Condition, cond_id)
    assert db_result.status == ConditionStatus.MET

@pytest.mark.asyncio
async def test_update_nonexistent_condition(client: AsyncClient):
    # Act
    update_payload = {"status": "Met"}
    response = await client.patch("/api/v1/messaging-conditions/conditions/99999", json=update_payload)
    
    # Assert
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_send_message_endpoint(client: AsyncClient):
    # Arrange
    payload = {
        "application_id": "app_msg_01",
        "recipient_type": "Applicant",
        "subject": "Application Status",
        "body": "Your file has been approved pending conditions.",
        "priority": "High"
    }
    
    # Act
    response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
    
    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["subject"] == "Application Status"
    assert data["status"] == "Sent" # Assuming default status

@pytest.mark.asyncio
async def test_get_messages_endpoint(client: AsyncClient, db_session: AsyncSession):
    # Arrange
    msg = Message(
        application_id="app_msg_history",
        recipient_type="Applicant",
        subject="Welcome",
        body="Welcome to the portal",
        created_by="system"
    )
    db_session.add(msg)
    await db_session.commit()
    
    # Act
    response = await client.get("/api/v1/messaging-conditions/messages?application_id=app_msg_history")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(m["subject"] == "Welcome" for m in data)

@pytest.mark.asyncio
async def test_pii_protection_in_logs(client: AsyncClient, caplog):
    """
    Test that sensitive data isn't logged.
    Note: In a real integration test, we might check the log output directly.
    Here we ensure the endpoint handles PII validation if configured.
    """
    # Arrange - Payload with potential PII pattern (SIN)
    payload = {
        "application_id": "app_pii_test",
        "recipient_type": "Applicant",
        "subject": "Update regarding SIN 123456789",
        "body": "Please verify info",
        "priority": "Normal"
    }
    
    # Act
    # Depending on implementation, this might return 400 or 422
    response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
    
    # Assert - If the service blocks PII
    # (Assuming the service implements this check as per regulations)
    # If the service doesn't block, this test documents the behavior.
    # For this exercise, we assume strict validation is active.
    assert response.status_code in [400, 422]

@pytest.mark.asyncio
async def test_audit_fields_immutable(client: AsyncClient, db_session: AsyncSession):
    """
    Regulatory: FINTRAC - Verify created_at/created_by are set and cannot be updated via API.
    """
    # Arrange
    payload = {
        "application_id": "app_audit_01",
        "description": "Audit Test",
        "condition_type": "Generic",
        "assigned_to": "user1"
    }
    resp = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
    cond_id = resp.json()["id"]
    original_created_at = resp.json()["created_at"]
    
    # Act - Try to update created_at (should be ignored or rejected by schema)
    update_payload = {
        "status": "Waived",
        "created_at": "2020-01-01T00:00:00" # Malicious attempt
    }
    update_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json=update_payload)
    
    # Assert
    assert update_resp.status_code == 200
    # Verify created_at did not change
    assert update_resp.json()["created_at"] == original_created_at

@pytest.mark.asyncio
async def test_validation_empty_description(client: AsyncClient):
    # Arrange
    payload = {
        "application_id": "app_val_01",
        "description": "", # Invalid
        "condition_type": "Generic",
        "assigned_to": "user1"
    }
    
    # Act
    response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
    
    # Assert
    assert response.status_code == 422 # Validation Error