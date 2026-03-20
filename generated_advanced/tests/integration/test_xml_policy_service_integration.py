import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicyRecord

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_upload_policy_success(app, db_session, valid_xml_payload):
    """
    Integration test: Upload valid XML via API endpoint.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/xml-policy/upload",
            content=valid_xml_payload,
            headers={"Content-Type": "application/xml"}
        )

    assert response.status_code == 201
    
    data = response.json()
    assert "id" in data
    assert data["application_id"] == "APP-12345"
    assert data["status"] == "Approved"
    assert data["premium_amount"] == "12500.50" # JSON serialization of Decimal
    assert data["certificate_number"] == "CERT-2023-X99"
    assert "created_at" in data

    # Verify Database Persistence
    stmt = select(XmlPolicyRecord).where(XmlPolicyRecord.id == data["id"])
    result = await db_session.execute(stmt)
    db_record = result.scalar_one_or_none()

    assert db_record is not None
    assert db_record.application_id == "APP-12345"
    assert db_record.raw_xml == valid_xml_payload

@pytest.mark.asyncio
async def test_upload_policy_malformed_xml(app, db_session, malformed_xml_payload):
    """
    Integration test: Upload malformed XML returns 400.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/xml-policy/upload",
            content=malformed_xml_payload,
            headers={"Content-Type": "application/xml"}
        )

    assert response.status_code == 400
    
    data = response.json()
    assert "detail" in data
    assert "error_code" in data
    # Check that error code matches the exception defined in exceptions.py
    assert data["error_code"] == "XML_PARSE_ERROR"

@pytest.mark.asyncio
async def test_upload_policy_invalid_schema(app, db_session, invalid_schema_payload):
    """
    Integration test: Upload XML with missing required fields returns 422.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/xml-policy/upload",
            content=invalid_schema_payload,
            headers={"Content-Type": "application/xml"}
        )

    assert response.status_code == 422 # Assuming validation error maps to 422
    
    data = response.json()
    assert "detail" in data
    assert "error_code" in data
    assert data["error_code"] == "XML_VALIDATION_ERROR"

@pytest.mark.asyncio
async def test_get_policy_record(app, db_session):
    """
    Integration test: Retrieve a stored policy record.
    """
    # 1. Create a record directly in DB
    new_record = XmlPolicyRecord(
        application_id="APP-GET-TEST",
        lender_id="LENDER-1",
        status="Approved",
        premium_amount=Decimal("1000.00"),
        certificate_number="CERT-GET",
        raw_xml="<dummy/>"
    )
    db_session.add(new_record)
    await db_session.commit()
    await db_session.refresh(new_record)

    # 2. Retrieve via API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/xml-policy/{new_record.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == new_record.id
    assert data["application_id"] == "APP-GET-TEST"
    # Ensure raw XML is NOT returned in the GET endpoint for security/PIPEDA minimization
    assert "raw_xml" not in data

@pytest.mark.asyncio
async def test_get_policy_not_found(app, db_session):
    """
    Integration test: Retrieve non-existent policy returns 404.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/xml-policy/99999")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_audit_fields_created(app, db_session, valid_xml_payload):
    """
    Integration test: Verify created_at and updated_at are set automatically.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/xml-policy/upload",
            content=valid_xml_payload,
            headers={"Content-Type": "application/xml"}
        )
    
    assert response.status_code == 201
    data = response.json()
    record_id = data["id"]

    # Verify in DB
    stmt = select(XmlPolicyRecord).where(XmlPolicyRecord.id == record_id)
    result = await db_session.execute(stmt)
    db_record = result.scalar_one_or_none()

    assert db_record.created_at is not None
    assert db_record.updated_at is not None
    # Assuming created_at and updated_at are roughly equal on creation
    assert (db_record.updated_at - db_record.created_at).total_seconds() < 1

@pytest.mark.asyncio
async def test_content_type_validation(app, db_session):
    """
    Integration test: Ensure endpoint rejects non-XML content types.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/xml-policy/upload",
            json={"some": "json"}, # Sending JSON instead of XML
            headers={"Content-Type": "application/json"}
        )

    # Expecting 415 Unsupported Media Type or 400 Bad Request depending on implementation
    assert response.status_code in [400, 415]
    
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_empty_body_upload(app, db_session):
    """
    Integration test: Handle empty request body.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/xml-policy/upload",
            content="",
            headers={"Content-Type": "application/xml"}
        )

    assert response.status_code == 400
    data = response.json()
    assert "error_code" in data or "detail" in data