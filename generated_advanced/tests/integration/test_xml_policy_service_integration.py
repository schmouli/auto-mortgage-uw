import pytest
from httpx import AsyncClient
from uuid import uuid4
from sqlalchemy import select

from mortgage_underwriting.modules.xml_policy.models import XMLPolicy

@pytest.mark.integration
class TestXMLPolicyRoutes:

    async def test_create_policy_endpoint_success(self, client: AsyncClient, valid_mortgage_policy_xml):
        """Test creating a policy via POST endpoint."""
        response = await client.post(
            "/api/v1/xml-policy/",
            json={"xml_content": valid_mortgage_policy_xml}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["xml_content"] == valid_mortgage_policy_xml
        assert data["checksum"] is not None
        assert "created_at" in data

    async def test_create_policy_endpoint_invalid_xml(self, client: AsyncClient, invalid_mortgage_policy_xml):
        """Test that invalid XML returns 422 Unprocessable Entity."""
        response = await client.post(
            "/api/v1/xml-policy/",
            json={"xml_content": invalid_mortgage_policy_xml}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "XML parsing failed" in data["detail"]

    async def test_create_policy_endpoint_empty_body(self, client: AsyncClient):
        """Test validation on empty input."""
        response = await client.post(
            "/api/v1/xml-policy/",
            json={}
        )
        
        # FastAPI validation error
        assert response.status_code == 422

    async def test_get_policy_endpoint_success(self, client: AsyncClient, db_session, valid_mortgage_policy_xml):
        """Test retrieving a stored policy via GET endpoint."""
        # 1. Create a policy directly in DB
        new_policy = XMLPolicy(
            xml_content=valid_mortgage_policy_xml,
            checksum="generated_checksum"
        )
        db_session.add(new_policy)
        await db_session.commit()
        await db_session.refresh(new_policy)

        # 2. Retrieve via API
        response = await client.get(f"/api/v1/xml-policy/{new_policy.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(new_policy.id)
        assert data["xml_content"] == valid_mortgage_policy_xml
        assert data["checksum"] == "generated_checksum"

    async def test_get_policy_endpoint_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent policy returns 404."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/xml-policy/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_list_policies_endpoint(self, client: AsyncClient, db_session, valid_mortgage_policy_xml):
        """Test listing policies with pagination."""
        # Create 3 policies
        for _ in range(3):
            policy = XMLPolicy(xml_content=valid_mortgage_policy_xml, checksum="hash")
            db_session.add(policy)
        await db_session.commit()

        response = await client.get("/api/v1/xml-policy/?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["total"] >= 3

    async def test_update_policy_endpoint(self, client: AsyncClient, db_session, valid_mortgage_policy_xml):
        """Test updating an existing policy."""
        # Create initial
        policy = XMLPolicy(xml_content=valid_mortgage_policy_xml, checksum="old_hash")
        db_session.add(policy)
        await db_session.commit()
        await db_session.refresh(policy)

        updated_xml = valid_mortgage_policy_xml.replace("1.0", "2.0")
        
        response = await client.put(
            f"/api/v1/xml-policy/{policy.id}",
            json={"xml_content": updated_xml}
        )

        assert response.status_code == 200
        data = response.json()
        assert "2.0" in data["xml_content"]
        assert data["checksum"] != "old_hash" # Checksum must change

    async def test_delete_policy_is_forbidden(self, client: AsyncClient, db_session, valid_mortgage_policy_xml):
        """
        Test that deleting a policy is forbidden (FINTRAC compliance).
        Ensure immutable audit trail is preserved.
        """
        policy = XMLPolicy(xml_content=valid_mortgage_policy_xml, checksum="hash")
        db_session.add(policy)
        await db_session.commit()

        # Assuming a DELETE endpoint might exist, it should return 403 or 405
        # If it doesn't exist, 405 Method Not Allowed is expected from FastAPI
        response = await client.delete(f"/api/v1/xml-policy/{policy.id}")
        
        assert response.status_code in [403, 404, 405] 

    async def test_xml_content_escaped_in_response(self, client: AsyncClient, db_session):
        """Test that XML content is properly handled in JSON response."""
        xml_with_special_chars = "<Policy><Name>Test & Co.</Name></Policy>"
        policy = XMLPolicy(xml_content=xml_with_special_chars, checksum="hash")
        db_session.add(policy)
        await db_session.commit()

        response = await client.get(f"/api/v1/xml-policy/{policy.id}")
        
        assert response.status_code == 200
        # JSON clients usually handle escaping, but we ensure the round trip preserves data
        assert "Test & Co." in response.json()["xml_content"]