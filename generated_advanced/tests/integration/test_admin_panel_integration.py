import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog, SystemConfig
from mortgage_underwriting.common.security import encrypt_pii

@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminPanelEndpoints:

    async def test_create_user_endpoint(self, client: AsyncClient, db_session, valid_admin_user_data):
        """
        Test creating a new admin user via API.
        Verify DB persistence and response structure.
        """
        # Act
        response = await client.post("/api/v1/admin/users", json=valid_admin_user_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == valid_admin_user_data["username"]
        assert "id" in data
        assert "password" not in data  # Ensure password is not leaked in response

        # Verify DB
        stmt = select(AdminUser).where(AdminUser.email == valid_admin_user_data["email"])
        result = await db_session.execute(stmt)
        db_user = result.scalar_one()
        assert db_user is not None
        assert db_user.is_active is True

    async def test_create_user_duplicate_email_conflict(self, client: AsyncClient, db_session, valid_admin_user_data):
        """
        Test that duplicate emails return 409 Conflict.
        """
        # Setup - Create first user
        response1 = await client.post("/api/v1/admin/users", json=valid_admin_user_data)
        assert response1.status_code == 201

        # Act - Try to create same user again
        response2 = await client.post("/api/v1/admin/users", json=valid_admin_user_data)

        # Assert
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    async def test_list_audit_logs_endpoint(self, client: AsyncClient, db_session):
        """
        Test retrieving audit logs with pagination.
        """
        # Setup - Create logs directly in DB
        log1 = AuditLog(action="CREATE_USER", actor_id="admin_1", details={})
        log2 = AuditLog(action="UPDATE_RATE", actor_id="admin_1", details={})
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/admin/audit-logs?limit=10")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2
        assert data["total"] >= 2

    async def test_update_system_config_endpoint(self, client: AsyncClient, db_session, valid_system_config_data):
        """
        Test updating a system configuration.
        Verify update persistence.
        """
        # Setup - Create config
        config = SystemConfig(**valid_system_config_data)
        db_session.add(config)
        await db_session.commit()

        # Act
        update_payload = {"value": "650"}
        response = await client.put(f"/api/v1/admin/config/{valid_system_config_data['key']}", json=update_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "650"
        
        # Verify DB
        await db_session.refresh(config)
        assert config.value == "650"

    async def test_update_stress_test_rate_validation(self, client: AsyncClient, db_session):
        """
        Regulatory: Ensure stress test rate update accepts valid decimal strings.
        """
        # Setup
        config = SystemConfig(key="stress_test_rate", value="5.25", description="Floor")
        db_session.add(config)
        await db_session.commit()

        # Act - Update to exactly 5.25% (OSFI B-20 floor)
        response = await client.put("/api/v1/admin/config/stress_test_rate", json={"value": "5.25"})

        # Assert
        assert response.status_code == 200
        
        # Act - Update to 5.50%
        response = await client.put("/api/v1/admin/config/stress_test_rate", json={"value": "5.50"})
        assert response.status_code == 200

    async def test_update_config_invalid_format(self, client: AsyncClient, db_session):
        """
        Test that updating a config with invalid data (e.g., text for numeric field) is handled.
        """
        # Setup
        config = SystemConfig(key="min_credit_score", value="600", description="Score")
        db_session.add(config)
        await db_session.commit()

        # Act
        response = await client.put("/api/v1/admin/config/min_credit_score", json={"value": "not_a_number"})

        # Assert
        # Depending on implementation, this might be 422 (validation) or 400
        assert response.status_code in [400, 422]

    async def test_get_audit_logs_filter_by_action(self, client: AsyncClient, db_session):
        """
        Test filtering audit logs by specific action.
        """
        # Setup
        log1 = AuditLog(action="LOGIN", actor_id="u1", details={})
        log2 = AuditLog(action="LOGOUT", actor_id="u1", details={})
        db_session.add_all([log1, log2])
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/admin/audit-logs?action=LOGIN")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["action"] == "LOGIN" for item in data["items"])

    async def test_delete_user_soft_delete(self, client: AsyncClient, db_session):
        """
        Verify that deleting a user performs a soft delete (sets is_active=False) 
        rather than removing the record (FINTRAC compliance).
        """
        # Setup
        user_data = {"username": "to_delete", "email": "del@test.com", "role": "viewer", "is_active": True}
        create_resp = await client.post("/api/v1/admin/users", json=user_data)
        user_id = create_resp.json()["id"]

        # Act
        response = await client.delete(f"/api/v1/admin/users/{user_id}")

        # Assert
        assert response.status_code == 204

        # Verify DB - User should still exist but be inactive
        stmt = select(AdminUser).where(AdminUser.id == user_id)
        result = await db_session.execute(stmt)
        db_user = result.scalar_one()
        assert db_user is not None # Record exists
        assert db_user.is_active is False # Soft deleted