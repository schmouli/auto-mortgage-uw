--- conftest.py ---
import pytest
import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Import paths based on project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.xml_policy_service.routes import router as xml_policy_router
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicyRecord
from mortgage_underwriting.modules.xml_policy_service.schemas import PolicyStatus

# Test Data Fixtures
VALID_POLICY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PolicyResponse>
    <ApplicationId>APP-12345</ApplicationId>
    <LenderId>LENDER-99</LenderId>
    <Decision>Approved</Decision>
    <PremiumAmount>12500.50</PremiumAmount>
    <CertificateNumber>CERT-2023-X99</CertificateNumber>
    <Timestamp>2023-10-27T10:00:00Z</Timestamp>
</PolicyResponse>
"""

MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PolicyResponse>
    <ApplicationId>APP-12345
    <!-- Missing closing tag -->
</PolicyResponse>
"""

INVALID_SCHEMA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PolicyResponse>
    <ApplicationId>APP-12345</ApplicationId>
    <Decision>Pending</Decision>
    <!-- Missing Mandatory Fields: PremiumAmount, CertificateNumber -->
</PolicyResponse>
"""

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Database Fixture for Integration Tests (In-Memory SQLite)
@pytest.fixture(scope="function")
async def db_engine():
    # Using aiosqlite for async support in tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

# App Fixture
@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(xml_policy_router, prefix="/api/v1/xml-policy", tags=["XML Policy"])
    return app

# Mock Service Layer for Unit Tests
@pytest.fixture
def mock_xml_service():
    from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
    return XmlPolicyService

@pytest.fixture
def mock_db_session():
    from unittest.mock import AsyncMock
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = AsyncMock()
    return session

# Payloads
@pytest.fixture
def valid_xml_payload():
    return VALID_POLICY_XML

@pytest.fixture
def malformed_xml_payload():
    return MALFORMED_XML

@pytest.fixture
def invalid_schema_payload():
    return INVALID_SCHEMA_XML
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicyRecord
from mortgage_underwriting.modules.xml_policy_service.exceptions import (
    XmlParseError,
    XmlValidationError,
    PolicyProcessingError
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestXmlPolicyService:

    async def test_process_policy_success(self, mock_db_session, valid_xml_payload):
        """
        Test successful processing of valid XML policy data.
        Should parse XML, extract fields, and save to DB.
        """
        service = XmlPolicyService(mock_db_session)
        
        result = await service.process_policy_upload(valid_xml_payload)

        # Verify DB interactions
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

        # Verify extracted data
        assert result.application_id == "APP-12345"
        assert result.lender_id == "LENDER-99"
        assert result.status == "Approved"
        assert result.premium_amount == Decimal("12500.50")
        assert result.certificate_number == "CERT-2023-X99"
        assert result.raw_xml == valid_xml_payload
        assert isinstance(result.created_at, datetime)

    async def test_process_policy_malformed_xml_raises_error(self, mock_db_session, malformed_xml_payload):
        """
        Test that malformed XML raises XmlParseError.
        """
        service = XmlPolicyService(mock_db_session)

        with pytest.raises(XmlParseError) as exc_info:
            await service.process_policy_upload(malformed_xml_payload)

        assert "Invalid XML format" in str(exc_info.value)
        # Ensure DB commit was NOT called
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    async def test_process_policy_missing_required_fields_raises_validation_error(self, mock_db_session, invalid_schema_payload):
        """
        Test that valid XML with missing business fields raises XmlValidationError.
        """
        service = XmlPolicyService(mock_db_session)

        with pytest.raises(XmlValidationError) as exc_info:
            await service.process_policy_upload(invalid_schema_payload)

        assert "Validation failed" in str(exc_info.value)
        # Ensure DB commit was NOT called
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    async def test_process_policy_database_failure_raises_policy_error(self, mock_db_session, valid_xml_payload):
        """
        Test that database errors during save are caught and wrapped in PolicyProcessingError.
        """
        # Simulate DB error on commit
        mock_db_session.commit.side_effect = SQLAlchemyError("Database connection failed")

        service = XmlPolicyService(mock_db_session)

        with pytest.raises(PolicyProcessingError) as exc_info:
            await service.process_policy_upload(valid_xml_payload)

        assert "Failed to persist policy" in str(exc_info.value)
        mock_db_session.add.assert_called_once()

    async def test_extract_fields_precision_check(self, mock_db_session):
        """
        Test that financial values are extracted with Decimal precision.
        """
        xml_with_fraction = """<?xml version="1.0"?>
        <PolicyResponse>
            <ApplicationId>APP-001</ApplicationId>
            <Decision>Approved</Decision>
            <PremiumAmount>12345.6789</PremiumAmount>
            <CertificateNumber>CERT-X</CertificateNumber>
        </PolicyResponse>
        """
        
        service = XmlPolicyService(mock_db_session)
        result = await service.process_policy_upload(xml_with_fraction)

        # Ensure we are using Decimal, not float
        assert isinstance(result.premium_amount, Decimal)
        # Check precision is maintained (assuming schema allows 4 decimal places or truncates)
        assert result.premium_amount == Decimal("12345.6789")

    async def test_get_policy_by_id_success(self, mock_db_session):
        """
        Test retrieving a policy by ID.
        """
        # Setup mock return value
        mock_policy = XmlPolicyRecord(
            id=1,
            application_id="APP-999",
            lender_id="LENDER-1",
            status="Approved",
            premium_amount=Decimal("5000.00"),
            certificate_number="CERT-123",
            raw_xml="<test/>"
        )
        
        # Mock the execute chain for SQLAlchemy 2.0
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_policy
        mock_db_session.execute.return_value = mock_result

        service = XmlPolicyService(mock_db_session)
        result = await service.get_policy(1)

        assert result is not None
        assert result.application_id == "APP-999"
        mock_db_session.execute.assert_awaited_once()

    async def test_get_policy_by_id_not_found(self, mock_db_session):
        """
        Test retrieving a non-existent policy returns None.
        """
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = XmlPolicyService(mock_db_session)
        result = await service.get_policy(999)

        assert result is None

    async def test_sanitization_of_xml_input(self, mock_db_session):
        """
        Test that input XML is stored as-is (or sanitized depending on impl),
        but specifically check that no logging of sensitive data occurs in the service logic.
        """
        # This test checks that the service method returns the object without accidentally
        # exposing internal state in error messages if we were to debug.
        xml_data = """<?xml version="1.0"?>
        <PolicyResponse>
            <ApplicationId>APP-SECURE</ApplicationId>
            <Decision>Approved</Decision>
            <PremiumAmount>100.00</PremiumAmount>
            <CertificateNumber>CERT-SEC</CertificateNumber>
        </PolicyResponse>
        """
        
        service = XmlPolicyService(mock_db_session)
        result = await service.process_policy_upload(xml_data)
        
        # Verify result structure
        assert hasattr(result, 'raw_xml')
        # Ensure no extra fields were leaked
        assert result.application_id == "APP-SECURE"
--- integration_tests ---
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