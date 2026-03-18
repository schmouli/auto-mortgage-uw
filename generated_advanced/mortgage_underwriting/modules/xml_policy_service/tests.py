--- conftest.py ---
import pytest
import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy
from mortgage_underwriting.modules.xml_policy_service.routes import router

# Database URL for in-memory SQLite (fast, isolated tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def engine():
    """Create a new engine for each test function."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def valid_policy_xml() -> str:
    """Returns a valid XML structure for underwriting policy."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Provider>CMHC</Provider>
        <Version>1.0</Version>
        <Rules>
            <MaxLTV>95.00</MaxLTV>
            <MinCreditScore>600</MinCreditScore>
            <StressTestThreshold>5.25</StressTestThreshold>
            <GDSLimit>39.00</GDSLimit>
            <TDSLimit>44.00</TDSLimit>
        </Rules>
    </MortgagePolicy>
    """

@pytest.fixture
def invalid_policy_xml() -> str:
    """Returns a malformed XML string."""
    return "<?xml version='1.0'?><MortgagePolicy><Provider>CMHC"

@pytest.fixture
def non_compliant_policy_xml() -> str:
    """Returns XML that violates OSFI B-20 limits (e.g., TDS > 44%)."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Provider>RiskyLender</Provider>
        <Version>1.0</Version>
        <Rules>
            <MaxLTV>99.00</MaxLTV>
            <TDSLimit>50.00</TDSLimit>
        </Rules>
    </MortgagePolicy>
    """

@pytest.fixture
def app() -> FastAPI:
    """Fixture for the FastAPI application."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policy-service", tags=["XML Policy"])
    return app

@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async client for integration testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy
from mortgage_underwriting.modules.xml_policy_service.schemas import XmlPolicyCreate, XmlPolicyResponse
from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestXmlPolicyService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return XmlPolicyService(mock_db)

    @pytest.mark.asyncio
    async def test_parse_xml_success(self, service, valid_policy_xml):
        """Test successful parsing of valid XML."""
        result = await service._parse_xml_content(valid_policy_xml)
        
        assert result is not None
        assert result["Provider"] == "CMHC"
        assert result["Version"] == "1.0"
        assert result["Rules"]["MaxLTV"] == "95.00"
        assert result["Rules"]["StressTestThreshold"] == "5.25"

    @pytest.mark.asyncio
    async def test_parse_xml_failure_malformed(self, service, invalid_policy_xml):
        """Test that parsing malformed XML raises AppException."""
        with pytest.raises(AppException) as exc_info:
            await service._parse_xml_content(invalid_policy_xml)
        
        assert exc_info.value.status_code == 400
        assert "XML parsing error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_compliance_osfi_b20_success(self, service, valid_policy_xml):
        """Test validation passes for OSFI B-20 compliant policy."""
        parsed_data = await service._parse_xml_content(valid_policy_xml)
        
        # Should not raise
        await service._validate_regulatory_compliance(parsed_data)

    @pytest.mark.asyncio
    async def test_validate_compliance_osfi_b20_failure_tds(self, service, non_compliant_policy_xml):
        """Test validation fails if TDS > 44% (OSFI B-20)."""
        parsed_data = await service._parse_xml_content(non_compliant_policy_xml)
        
        with pytest.raises(AppException) as exc_info:
            await service._validate_regulatory_compliance(parsed_data)
        
        assert exc_info.value.status_code == 400
        assert "OSFI B-20" in exc_info.value.detail
        assert "TDS" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_policy_success(self, service, mock_db, valid_policy_xml):
        """Test successful creation of a policy record."""
        payload = XmlPolicyCreate(xml_content=valid_policy_xml)
        
        # Mock the return value of refresh
        mock_policy = XmlPolicy(
            id=1,
            xml_content_hash="abc123",
            provider="CMHC",
            version="1.0",
            rules={"MaxLTV": "95.00"},
            status="active"
        )
        mock_db.refresh.return_value = mock_policy

        result = await service.create_policy(payload)

        assert isinstance(result, XmlPolicyResponse)
        assert result.provider == "CMHC"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_policy_database_error(self, service, mock_db, valid_policy_xml):
        """Test handling of database errors during creation."""
        payload = XmlPolicyCreate(xml_content=valid_policy_xml)
        
        mock_db.commit.side_effect = SQLAlchemyError("DB connection failed")

        with pytest.raises(AppException) as exc_info:
            await service.create_policy(payload)
        
        assert exc_info.value.status_code == 500
        assert "Database error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_policy_by_id_success(self, service, mock_db):
        """Test retrieving a policy by ID."""
        mock_policy = XmlPolicy(
            id=1,
            xml_content_hash="hash1",
            provider="TestProvider",
            version="1.0",
            rules={},
            status="active"
        )
        
        # Mock the scalar result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_policy
        mock_db.execute.return_value = mock_result

        result = await service.get_policy(1)
        
        assert result is not None
        assert result.id == 1
        assert result.provider == "TestProvider"

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, service, mock_db):
        """Test retrieving a non-existent policy."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(AppException) as exc_info:
            await service.get_policy(999)
        
        assert exc_info.value.status_code == 404
        assert "Policy not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_decimal_conversion_in_rules(self, service, valid_policy_xml):
        """Test that financial values in XML are converted to Decimals."""
        parsed_data = await service._parse_xml_content(valid_policy_xml)
        rules = service._convert_rules_to_decimals(parsed_data["Rules"])
        
        # Verify Decimal conversion (Mandatory for financial values)
        assert isinstance(rules["MaxLTV"], Decimal)
        assert rules["MaxLTV"] == Decimal("95.00")
        assert isinstance(rules["StressTestThreshold"], Decimal)
        assert rules["StressTestThreshold"] == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_redact_pii_from_xml_logs(self, service, valid_policy_xml):
        """Test that PII is redacted if accidentally present in XML (PIPEDA)."""
        # Simulate XML with SIN
        dirty_xml = """<?xml version="1.0"?>
        <MortgagePolicy><SIN>123456789</SIN><Rules><MaxLTV>80</MaxLTV></Rules></MortgagePolicy>
        """
        
        # The service should strip/hash sensitive tags before storing/logging
        # Assuming a helper method exists or is part of processing
        clean_data = await service._parse_xml_content(dirty_xml)
        
        # Ensure SIN is not stored in plain text in the parsed data structure
        assert "SIN" not in clean_data or clean_data["SIN"] != "123456789"

--- integration_tests ---
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