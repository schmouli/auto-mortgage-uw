```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.admin_panel.models import User, AuditLog
from mortgage_underwriting.modules.admin_panel.schemas import UserRole

@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminPanelEndpoints:

    async def test_create_user_endpoint(self, client: AsyncClient, db_session):
        """Test creating a new user via API."""
        payload = {
            "username": "jdoe_integration",
            "email": "jdoe@example.com",
            "full_name": "John Doe",
            "role": "underwriter",
            "sin": "123456789",
            "password": "StrongPass123!"
        }
        
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "jdoe_integration"
        assert data["email"] == "jdoe@example.com"
        assert data["role"] == "underwriter"
        assert "id" in data
        assert "password" not in data  # Ensure password is not in response
        assert "sin" not in data      # Ensure SIN is not in response (PIPEDA)
        assert "sin_hash" not in data # Ensure hash is not leaked

        # Verify DB state
        stmt = select(User).where(User.username == "jdoe_integration")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.sin_hash is not None
        assert user.sin_hash != "123456789"

    async def test_create_user_duplicate_email_conflict(self, client: AsyncClient, db_session):
        """Test that duplicate email returns 409 Conflict."""
        payload = {
            "username": "user1",
            "email": "duplicate@example.com",
            "full_name": "User One",
            "role": "underwriter",
            "sin": "111111111",
            "password": "Pass123!"
        }
        
        # Create first user
        await client.post("/api/v1/admin/users", json=payload)
        
        # Try to create second user with same email but different username
        payload["username"] = "user2"
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 409
        assert "detail" in response.json()

    async def test_get_users_list(self, client: AsyncClient, db_session):
        """Test retrieving a list of users."""
        # Seed data directly into DB
        user1 = User(
            username="admin_user", 
            email="admin@test.com", 
            role="admin",
            sin_hash="hash1",
            password_hash="pass1"
        )
        user2 = User(
            username="underwriter_user", 
            email="uw@test.com", 
            role="underwriter",
            sin_hash="hash2",
            password_hash="pass2"
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()
        
        response = await client.get("/api/v1/admin/users")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        # Verify PII protection
        for user in data["items"]:
            assert "sin" not in user
            assert "password" not in user

    async def test_get_audit_logs_endpoint(self, client: AsyncClient, db_session):
        """Test retrieving audit logs."""
        # Seed audit log
        log = AuditLog(
            action="USER_CREATED",
            entity_type="User",
            entity_id="user-123",
            performed_by="admin-1",
            details={"username": "new_user"}
        )
        db_session.add(log)
        await db_session.commit()
        
        response = await client.get("/api/v1/admin/audit-logs")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["action"] == "USER_CREATED"
        assert data[0]["performed_by"] == "admin-1"

    async def test_update_user_role_endpoint(self, client: AsyncClient, db_session):
        """Test updating a user's role via API."""
        # Create user
        create_payload = {
            "username": "promote_me",
            "email": "promote@test.com",
            "full_name": "Promote Me",
            "role": "underwriter",
            "sin": "999999999",
            "password": "Pass123!"
        }
        create_resp = await client.post("/api/v1/admin/users", json=create_payload)
        user_id = create_resp.json()["id"]
        
        # Update role
        update_payload = {"role": "admin"}
        update_resp = await client.patch(f"/api/v1/admin/users/{user_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        assert update_resp.json()["role"] == "admin"
        
        # Verify Audit Log was created for this action
        stmt = select(AuditLog).where(AuditLog.action == "ROLE_UPDATED")
        result = await db_session.execute(stmt)
        audit_log = result.scalar_one_or_none()
        assert audit_log is not None
        assert audit_log.entity_id == str(user_id)

    async def test_get_user_by_id(self, client: AsyncClient, db_session):
        """Test retrieving a specific user by ID."""
        payload = {
            "username": "single_user",
            "email": "single@test.com",
            "full_name": "Single User",
            "role": "underwriter",
            "sin": "555555555",
            "password": "Pass123!"
        }
        create_resp = await client.post("/api/v1/admin/users", json=payload)
        user_id = create_resp.json()["id"]
        
        response = await client.get(f"/api/v1/admin/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["username"] == "single_user"

    async def test_invalid_role_payload(self, client: AsyncClient):
        """Test validation error for invalid role during creation."""
        payload = {
            "username": "bad_role",
            "email": "bad@test.com",
            "full_name": "Bad Role",
            "role": "hacker", # Invalid
            "sin": "000000000",
            "password": "Pass123!"
        }
        
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_delete_user_forbidden(self, client: AsyncClient, db_session):
        """Test that deleting a user is handled correctly (e.g., soft delete or forbidden)."""
        # Assuming system policy prevents deletion of users for audit trail purposes
        # Or if deletion is allowed, it should be a soft delete.
        # Here we test if the endpoint exists and handles the request appropriately.
        # Based on FINTRAC, usually we don't delete, we deactivate.
        
        payload = {
            "username": "delete_me",
            "email": "delete@test.com",
            "full_name": "Delete Me",
            "role": "underwriter",
            "sin": "123123123",
            "password": "Pass123!"
        }
        create_resp = await client.post("/api/v1/admin/users", json=payload)
        user_id = create_resp.json()["id"]
        
        # Attempt delete
        response = await client.delete(f"/api/v1/admin/users/{user_id}")
        
        # Expect 405 Method Not Allowed or 403 Forbidden depending on implementation
        # Assuming it is not allowed to maintain audit trail
        assert response.status_code in [405, 403]

    async def test_health_check(self, client: AsyncClient):
        """Test the health check endpoint for the admin module."""
        response = await client.get("/api/v1/admin/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
```