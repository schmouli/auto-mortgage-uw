--- conftest.py ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock

# Base setup for tests
class Base(DeclarativeBase):
    pass

# Mock Model for testing if actual model isn't imported
# In a real scenario, this would be imported from models.py
class XmlPolicy(Base):
    __tablename__ = "xml_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    policy_name: Mapped[str] = mapped_column(index=True)
    version: Mapped[str]
    content: Mapped[str]
    min_credit_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    max_ltv: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

# Fixtures
@pytest.fixture
def valid_policy_xml() -> str:
    """Returns a valid XML string for a mortgage policy."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Header>
            <Name>StandardResidential</Name>
            <Version>1.0</Version>
        </Header>
        <UnderwritingRules>
            <MinCreditScore>680</MinCreditScore>
            <MaxLTV>80.00</MaxLTV>
            <StressTestRate>5.25</StressTestRate>
        </UnderwritingRules>
    </MortgagePolicy>
    """

@pytest.fixture
def invalid_policy_xml() -> str:
    """Returns a malformed XML string."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Header>
            <Name>BrokenPolicy
    </MortgagePolicy>
    """

@pytest.fixture
def missing_fields_xml() -> str:
    """Returns XML with missing mandatory fields."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Header>
            <Name>IncompletePolicy</Name>
        </Header>
    </MortgagePolicy>
    """

@pytest.fixture
def mock_db_session():
    """Provides a mock AsyncSession for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session

@pytest.fixture
def sample_policy_dict():
    """Returns a dictionary representation of a parsed policy."""
    return {
        "policy_name": "StandardResidential",
        "version": "1.0",
        "min_credit_score": 680,
        "max_ltv": Decimal("80.00"),
        "stress_test_rate": Decimal("5.25")
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree.ElementTree import ParseError

from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService
from mortgage_underwriting.modules.xml_policy_service.exceptions import (
    XmlParseError,
    PolicyValidationError,
    InvalidPolicySchema
)

# Assuming models exist as per project structure
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy

@pytest.mark.unit
class TestXmlPolicyService:

    @pytest.mark.asyncio
    async def test_parse_xml_success(self, valid_policy_xml):
        """Test successful parsing of valid XML content."""
        service = XmlPolicyService()
        result = await service.parse_xml_content(valid_policy_xml)
        
        assert result is not None
        assert result["policy_name"] == "StandardResidential"
        assert result["version"] == "1.0"
        assert result["min_credit_score"] == 680
        # Ensure financial values are Decimal
        assert isinstance(result["max_ltv"], Decimal)
        assert result["max_ltv"] == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_parse_xml_malformed_raises_error(self, invalid_policy_xml):
        """Test that parsing malformed XML raises XmlParseError."""
        service = XmlPolicyService()
        
        with pytest.raises(XmlParseError) as exc_info:
            await service.parse_xml_content(invalid_policy_xml)
        
        assert "Failed to parse XML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_policy_rules_success(self, sample_policy_dict):
        """Test validation logic with correct data types and ranges."""
        service = XmlPolicyService()
        # Should not raise
        await service.validate_policy_rules(sample_policy_dict)

    @pytest.mark.asyncio
    async def test_validate_policy_missing_field_raises(self, missing_fields_xml):
        """Test that missing mandatory fields trigger validation error."""
        service = XmlPolicyService()
        
        # First parse the incomplete XML
        parsed_data = await service.parse_xml_content(missing_fields_xml)
        
        with pytest.raises(PolicyValidationError) as exc_info:
            await service.validate_policy_rules(parsed_data)
            
        assert "Missing required field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_policy_invalid_ltv_type(self, sample_policy_dict):
        """Test that non-decimal LTV values are rejected."""
        service = XmlPolicyService()
        sample_policy_dict["max_ltv"] = "high" # Invalid type
        
        with pytest.raises(PolicyValidationError) as exc_info:
            await service.validate_policy_rules(sample_policy_dict)
        
        assert "Invalid format for max_ltv" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_policy_success(self, mock_db_session, valid_policy_xml):
        """Test successful creation of a policy record in DB."""
        service = XmlPolicyService(mock_db_session)
        
        result = await service.create_policy(valid_policy_xml)
        
        assert isinstance(result, XmlPolicy)
        assert result.policy_name == "StandardResidential"
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_policy_rollback_on_parse_error(self, mock_db_session, invalid_policy_xml):
        """Test that DB transaction is rolled back if parsing fails."""
        service = XmlPolicyService(mock_db_session)
        
        with pytest.raises(XmlParseError):
            await service.create_policy(invalid_policy_xml)
            
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_policy_by_id(self, mock_db_session):
        """Test retrieving a policy by ID."""
        # Setup mock return
        mock_policy = XmlPolicy(
            id=1, 
            policy_name="Test", 
            version="1.0", 
            content="<test/>",
            min_credit_score=600,
            max_ltv=Decimal("90.00")
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_policy
        mock_db_session.execute.return_value = mock_result

        service = XmlPolicyService(mock_db_session)
        result = await service.get_policy(1)
        
        assert result is not None
        assert result.id == 1
        assert result.policy_name == "Test"

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, mock_db_session):
        """Test retrieving a non-existent policy returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = XmlPolicyService(mock_db_session)
        result = await service.get_policy(999)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_audit_fields_set_on_create(self, mock_db_session, valid_policy_xml):
        """Test that created_at and updated_at are set automatically."""
        service = XmlPolicyService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.xml_policy_service.services.datetime") as mock_datetime:
            now = datetime.utcnow()
            mock_datetime.utcnow.return_value = now
            
            result = await service.create_policy(valid_policy_xml)
            
            assert result.created_at == now
            assert result.updated_at == now
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.xml_policy_service.routes import router
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy
from mortgage_underwriting.common.database import get_async_session, Base

# We use an in-memory SQLite for integration tests to ensure speed and isolation
# but still test the DB interaction logic.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def app():
    """Sets up a test FastAPI app with a test database."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    
    # Create engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Dependency override
    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policies", tags=["xml-policies"])
    app.dependency_overrides[get_async_session] = override_get_db

    yield app

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestXmlPolicyEndpoints:

    async def test_create_policy_endpoint_success(self, app: FastAPI, valid_policy_xml):
        """Test full workflow: POST request -> DB Save -> Response"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": valid_policy_xml}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["policy_name"] == "StandardResidential"
            assert data["min_credit_score"] == 680
            assert data["max_ltv"] == "80.00" # JSON serialization converts Decimal to string
            assert "created_at" in data

    async def test_create_policy_endpoint_malformed_xml(self, app: FastAPI, invalid_policy_xml):
        """Test endpoint rejection of malformed XML."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": invalid_policy_xml}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "XmlParseError" in data["detail"] or "Failed to parse" in data["detail"]

    async def test_create_policy_endpoint_missing_content(self, app: FastAPI):
        """Test endpoint validation for missing payload."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policies",
                json={}
            )
            
            assert response.status_code == 422  # Validation Error

    async def test_get_policy_endpoint_success(self, app: FastAPI, valid_policy_xml):
        """Test retrieving a previously created policy."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create
            create_resp = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": valid_policy_xml}
            )
            policy_id = create_resp.json()["id"]

            # 2. Get
            get_resp = await client.get(f"/api/v1/xml-policies/{policy_id}")
            
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == policy_id
            assert data["content"] == valid_policy_xml

    async def test_get_policy_endpoint_not_found(self, app: FastAPI):
        """Test 404 when policy does not exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/xml-policies/99999")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    async def test_list_policies_endpoint(self, app: FastAPI, valid_policy_xml):
        """Test listing all policies."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a couple
            await client.post("/api/v1/xml-policies", json={"xml_content": valid_policy_xml})
            await client.post("/api/v1/xml-policies", json={"xml_content": valid_policy_xml})

            # List
            response = await client.get("/api/v1/xml-policies")
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) >= 2

    async def test_update_policy_endpoint(self, app: FastAPI, valid_policy_xml):
        """Test updating an existing policy."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            create_resp = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": valid_policy_xml}
            )
            policy_id = create_resp.json()["id"]

            # Update
            updated_xml = valid_policy_xml.replace("StandardResidential", "UpdatedPolicy")
            update_resp = await client.put(
                f"/api/v1/xml-policies/{policy_id}",
                json={"xml_content": updated_xml}
            )

            assert update_resp.status_code == 200
            data = update_resp.json()
            assert data["policy_name"] == "UpdatedPolicy"
            # Check audit field
            assert data["updated_at"] != create_resp.json()["updated_at"]
```