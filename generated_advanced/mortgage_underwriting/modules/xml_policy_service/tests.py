--- conftest.py ---
import pytest
import asyncio
from datetime import datetime
from uuid import uuid4
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.xml_policy.models import XMLPolicy
from mortgage_underwriting.modules.xml_policy.routes import router
from mortgage_underwriting.main import app # Assuming main app exists or we construct it

# Fixture for valid XML data mimicking a mortgage policy
@pytest.fixture
def valid_mortgage_policy_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <LenderId>LENDER-001</LenderId>
        <PolicyVersion>1.0</PolicyVersion>
        <UnderwritingRules>
            <MaxLTV>0.95</MaxLTV>
            <MinCreditScore>680</MinCreditScore>
        </UnderwritingRules>
    </MortgagePolicy>"""

@pytest.fixture
def invalid_mortgage_policy_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <LenderId>LENDER-001
    </MortgagePolicy>""" # Missing closing tag and value

# Unit Test Fixtures

@pytest.fixture
def mock_db_session():
    """Provides a mock AsyncSession for unit tests."""
    from unittest.mock import AsyncMock
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session

# Integration Test Fixtures

@pytest.fixture(scope="function")
async def async_engine():
    """Creates an in-memory SQLite engine for integration tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Creates a new database session for a test."""
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def test_app():
    """Constructs a test FastAPI app including the XML Policy router."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policy", tags=["XML Policy"])
    return app

@pytest.fixture(scope="function")
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Provides an HTTPX async client for integration testing."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.xml_policy.services import XMLPolicyService
from mortgage_underwriting.modules.xml_policy.schemas import XMLPolicyCreate, XMLPolicyResponse
from mortgage_underwriting.modules.xml_policy.exceptions import XMLValidationError, PolicyStorageError
from mortgage_underwriting.modules.xml_policy.models import XMLPolicy

@pytest.mark.unit
class TestXMLPolicyService:

    @pytest.mark.asyncio
    async def test_validate_policy_success(self, valid_mortgage_policy_xml):
        """Test that valid XML passes validation without raising exceptions."""
        service = XMLPolicyService(db=AsyncMock())
        # Should not raise
        await service.validate_xml_content(valid_mortgage_policy_xml)

    @pytest.mark.asyncio
    async def test_validate_policy_invalid_xml_raises(self, invalid_mortgage_policy_xml):
        """Test that invalid XML raises XMLValidationError."""
        service = XMLPolicyService(db=AsyncMock())
        with pytest.raises(XMLValidationError) as exc_info:
            await service.validate_xml_content(invalid_mortgage_policy_xml)
        assert "XML parsing failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_policy_success(self, mock_db_session, valid_mortgage_policy_xml):
        """Test successful creation of a policy record."""
        payload = XMLPolicyCreate(xml_content=valid_mortgage_policy_xml)
        
        # Mock the return value of refresh to simulate DB returning an ID
        def mock_refresh(instance):
            instance.id = "123e4567-e89b-12d3-a456-426614174000"
            instance.created_at = datetime.utcnow()
            instance.updated_at = datetime.utcnow()
            
        mock_db_session.refresh.side_effect = mock_refresh

        service = XMLPolicyService(db=mock_db_session)
        result = await service.create_policy(payload)

        assert isinstance(result, XMLPolicyResponse)
        assert result.id == "123e4567-e89b-12d3-a456-426614174000"
        assert result.xml_content == valid_mortgage_policy_xml
        assert result.checksum is not None # Ensure integrity hash was generated
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_policy_generates_checksum(self, mock_db_session, valid_mortgage_policy_xml):
        """Test that creating a policy generates a SHA256 checksum for audit trail."""
        payload = XMLPolicyCreate(xml_content=valid_mortgage_policy_xml)
        
        def mock_refresh(instance):
            instance.id = uuid4()
            instance.created_at = datetime.utcnow()
            
        mock_db_session.refresh.side_effect = mock_refresh

        service = XMLPolicyService(db=mock_db_session)
        result = await service.create_policy(payload)

        # Verify checksum is not empty and is a string
        assert result.checksum
        assert len(result.checksum) == 64 # SHA256 length

    @pytest.mark.asyncio
    async def test_create_policy_db_failure_raises(self, mock_db_session, valid_mortgage_policy_xml):
        """Test that database errors are wrapped in PolicyStorageError."""
        payload = XMLPolicyCreate(xml_content=valid_mortgage_policy_xml)
        mock_db_session.commit.side_effect = SQLAlchemyError("Connection failed")

        service = XMLPolicyService(db=mock_db_session)
        
        with pytest.raises(PolicyStorageError) as exc_info:
            await service.create_policy(payload)
        
        assert "Failed to store policy" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_policy_by_id_success(self, mock_db_session):
        """Test retrieving a policy by ID."""
        policy_id = uuid4()
        mock_policy = XMLPolicy(
            id=policy_id,
            xml_content="<test>data</test>",
            checksum="abc123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Mock the scalar result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_policy
        mock_db_session.execute.return_value = mock_result

        service = XMLPolicyService(db=mock_db_session)
        result = await service.get_policy_by_id(policy_id)

        assert result is not None
        assert result.id == str(policy_id)
        assert result.xml_content == "<test>data</test>"

    @pytest.mark.asyncio
    async def test_get_policy_by_id_not_found(self, mock_db_session):
        """Test retrieving a non-existent policy returns None."""
        policy_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = XMLPolicyService(db=mock_db_session)
        result = await service.get_policy_by_id(policy_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_max_ltv_from_xml(self, valid_mortgage_policy_xml):
        """Test extraction logic for financial data (LTV) from XML."""
        service = XMLPolicyService(db=AsyncMock())
        ltv = await service.extract_max_ltv(valid_mortgage_policy_xml)
        
        assert ltv == Decimal("0.95")

    @pytest.mark.asyncio
    async def test_extract_max_ltv_missing_field(self):
        """Test extraction logic handles missing fields gracefully."""
        bad_xml = """<?xml version="1.0"?><Policy><NoLTV>1.0</NoLTV></Policy>"""
        service = XMLPolicyService(db=AsyncMock())
        
        with pytest.raises(XMLValidationError) as exc_info:
            await service.extract_max_ltv(bad_xml)
        
        assert "MaxLTV" in str(exc_info.value.detail)

--- integration_tests ---
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