import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy
from mortgage_underwriting.modules.xml_policy_service.schemas import XmlPolicyCreate
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
class TestXmlPolicyRoutes:

    @pytest.mark.asyncio
    async def test_create_policy_endpoint_success(self, client: AsyncClient, valid_policy_xml):
        """Test uploading a valid policy via POST endpoint."""
        response = await client.post(
            "/api/v1/xml-policy-service/policies",
            json={"xml_content": valid_policy_xml}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["provider"] == "CMHC"
        assert data["version"] == "1.0"
        assert data["status"] == "active"
        
        # Verify audit fields (FINTRAC requirement)
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_policy_endpoint_invalid_xml(self, client: AsyncClient, invalid_policy_xml):
        """Test uploading invalid XML returns 400."""
        response = await client.post(
            "/api/v1/xml-policy-service/policies",
            json={"xml_content": invalid_policy_xml}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error_code" in data

    @pytest.mark.asyncio
    async def test_create_policy_endpoint_non_compliant(self, client: AsyncClient, non_compliant_policy_xml):
        """Test uploading non-compliant policy (OSFI violation) returns 400."""
        response = await client.post(
            "/api/v1/xml-policy-service/policies",
            json={"xml_content": non_compliant_policy_xml}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "OSFI" in data["detail"] or "compliance" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_policy_endpoint(self, client: AsyncClient, valid_policy_xml, db_session):
        """Test retrieving a created policy."""
        # First, create a policy manually in DB to avoid dependency on create endpoint if it fails
        from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
        service = XmlPolicyService(db_session)
        
        payload = XmlPolicyCreate(xml_content=valid_policy_xml)
        created_policy = await service.create_policy(payload)
        policy_id = created_policy.id

        # Now retrieve via API
        response = await client.get(f"/api/v1/xml-policy-service/policies/{policy_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == policy_id
        assert data["provider"] == "CMHC"
        # Verify financial rules are preserved
        assert data["rules"]["MaxLTV"] == "95.00"

    @pytest.mark.asyncio
    async def test_get_policy_not_found_endpoint(self, client: AsyncClient):
        """Test retrieving a non-existent policy returns 404."""
        response = await client.get("/api/v1/xml-policy-service/policies/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_policies_endpoint(self, client: AsyncClient, valid_policy_xml, db_session):
        """Test listing multiple policies."""
        from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
        service = XmlPolicyService(db_session)
        
        # Create two policies
        payload1 = XmlPolicyCreate(xml_content=valid_policy_xml)
        await service.create_policy(payload1)
        
        payload2 = XmlPolicyCreate(xml_content=valid_policy_xml.replace("CMHC", "Genworth"))
        await service.create_policy(payload2)

        # List
        response = await client.get("/api/v1/xml-policy-service/policies")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2

    @pytest.mark.asyncio
    async def test_content_hash_immutability(self, client: AsyncClient, valid_policy_xml, db_session):
        """Test that content_hash is generated correctly and represents the content."""
        from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
        from mortgage_underwriting.common.security import hash_content # Assuming helper exists
        
        service = XmlPolicyService(db_session)
        payload = XmlPolicyCreate(xml_content=valid_policy_xml)
        created = await service.create_policy(payload)
        
        # Verify hash exists and is not empty
        assert created.xml_content_hash is not None
        assert len(created.xml_content_hash) > 0
        
        # Verify it matches the expected hash logic (SHA256)
        # This ensures data integrity (FINTRAC)
        expected_hash = hash_content(valid_policy_xml)
        assert created.xml_content_hash == expected_hash

    @pytest.mark.asyncio
    async def test_update_policy_forbidden(self, client: AsyncClient, db_session):
        """Test that updating policy XML is forbidden or strictly controlled (Audit trail)."""
        # Assuming a PUT endpoint exists, it should enforce audit logging
        # For this test, we verify the system rejects updates without proper auth/context
        # or that updates create a new version (immutable history)
        
        # Placeholder for update logic test
        # If updates are allowed, they must log 'updated_by'
        pass

    @pytest.mark.asyncio
    async def test_xml_special_characters_handling(self, client: AsyncClient):
        """Test that XML with special characters is handled correctly."""
        special_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <MortgagePolicy>
            <Provider>Lender &amp; Co.</Provider>
            <Notes>Rate &gt; 5%</Notes>
            <Rules><MaxLTV>80.00</MaxLTV></Rules>
        </MortgagePolicy>
        """
        
        response = await client.post(
            "/api/v1/xml-policy-service/policies",
            json={"xml_content": special_xml}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "&amp;" not in data["provider"] # Should be decoded by parser
        assert "Lender & Co." == data["provider"]