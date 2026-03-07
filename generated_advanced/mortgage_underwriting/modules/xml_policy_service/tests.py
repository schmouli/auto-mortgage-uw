--- conftest.py ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from mortgage_underwriting.common.database import Base

# Hypothetical Model for XML Policy Service (for testing purposes)
# In a real scenario, this would be imported from the module's models.py
class XmlPolicyRecord(Base):
    __tablename__ = "xml_policy_records"
    
    id = int
    policy_id = str
    raw_xml_hash = str
    premium_amount = Decimal
    ltv_ratio = Decimal
    insurance_required = bool
    created_at = datetime

@pytest.fixture(scope="function")
async def db_session():
    """
    Creates a fresh in-memory SQLite database for each test.
    """
    # Using SQLite for testing speed; in production this would be PostgreSQL
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        yield session
        
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def valid_policy_xml() -> str:
    """
    Valid CMHC-style XML policy data.
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Header>
            <PolicyId>POL-2023-001</PolicyId>
            <Timestamp>2023-10-27T10:00:00Z</Timestamp>
        </Header>
        <Financials>
            <LoanAmount>350000.00</LoanAmount>
            <PropertyValue>400000.00</PropertyValue>
            <Premium>8750.00</Premium>
            <LTV>87.50</LTV>
        </Financials>
        <Applicant>
            <SINHash>sha256_hash_value</SINHash>
            <CreditScore>720</CreditScore>
        </Applicant>
    </MortgagePolicy>
    """

@pytest.fixture
def high_risk_policy_xml() -> str:
    """
    XML with LTV > 95% (Should trigger CMHC rejection or specific handling).
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Header>
            <PolicyId>POL-HIGH-RISK</PolicyId>
        </Header>
        <Financials>
            <LoanAmount>380000.00</LoanAmount>
            <PropertyValue>400000.00</PropertyValue>
            <Premium>15200.00</Premium>
            <LTV>95.00</LTV>
        </Financials>
    </MortgagePolicy>
    """

@pytest.fixture
def invalid_malformed_xml() -> str:
    """
    Malformed XML missing closing tags.
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Header>
            <PolicyId>POL-BROKEN
    """

@pytest.fixture
def xml_with_float_precision_error() -> str:
    """
    XML containing non-standard numeric formats that might cause float/decimal issues.
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Financials>
            <LoanAmount>100000.999</LoanAmount>
            <PropertyValue>200000.001</PropertyValue>
        </Financials>
    </MortgagePolicy>
    """

@pytest.fixture
def mock_db():
    """
    Generic async mock DB for unit tests where we don't want a real DB connection.
    """
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db

--- unit_tests ---
import pytest
from decimal import Decimal, InvalidOperation
from unittest.mock import patch, AsyncMock, MagicMock
from mortgage_underwriting.modules.xml_policy.services import XmlPolicyService
from mortgage_underwriting.modules.xml_policy.exceptions import (
    XmlParseError,
    PolicyValidationError,
    InvalidFinancialDataError
)
from mortgage_underwriting.common.exceptions import AppException

# Assuming these imports based on project structure
# If models don't exist yet, these tests serve as the definition of behavior

@pytest.mark.unit
class TestXmlPolicyService:
    
    @pytest.fixture
    def service(self, mock_db):
        return XmlPolicyService(mock_db)

    @pytest.mark.asyncio
    async def test_parse_valid_xml_success(self, service, valid_policy_xml):
        """
        Test parsing valid XML returns correct data structure.
        """
        result = await service.parse_xml_content(valid_policy_xml)
        
        assert result["policy_id"] == "POL-2023-001"
        assert result["premium"] == Decimal("8750.00")
        assert result["ltv"] == Decimal("87.50")
        assert result["insurance_required"] is True # LTV > 80%

    @pytest.mark.asyncio
    async def test_parse_malformed_xml_raises_error(self, service, invalid_malformed_xml):
        """
        Test that malformed XML raises XmlParseError.
        """
        with pytest.raises(XmlParseError) as exc_info:
            await service.parse_xml_content(invalid_malformed_xml)
        
        assert "XML parsing failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decimal_precision_handling(self, service, xml_with_float_precision_error):
        """
        Test that financial values are strictly converted to Decimal without loss.
        """
        result = await service.parse_xml_content(xml_with_float_precision_error)
        
        # Ensure strict Decimal conversion, not float approximation
        assert isinstance(result["loan_amount"], Decimal)
        assert result["loan_amount"] == Decimal("100000.999")
        assert result["property_value"] == Decimal("200000.001")

    @pytest.mark.asyncio
    async def test_insurance_requirement_logic_boundary_80_percent(self, service, valid_policy_xml):
        """
        Test CMHC Rule: LTV > 80% requires insurance.
        Edge case: 80.01% should require it.
        """
        xml_80_01 = valid_policy_xml.replace("<LTV>87.50</LTV>", "<LTV>80.01</LTV>")
        result = await service.parse_xml_content(xml_80_01)
        
        assert result["ltv"] == Decimal("80.01")
        assert result["insurance_required"] is True

    @pytest.mark.asyncio
    async def test_insurance_requirement_logic_boundary_exactly_80(self, service, valid_policy_xml):
        """
        Test CMHC Rule: LTV <= 80% does NOT require insurance.
        """
        xml_80_00 = valid_policy_xml.replace("<LTV>87.50</LTV>", "<LTV>80.00</LTV>")
        result = await service.parse_xml_content(xml_80_00)
        
        assert result["ltv"] == Decimal("80.00")
        assert result["insurance_required"] is False

    @pytest.mark.asyncio
    async def test_validate_policy_rejects_high_ltv(self, service, high_risk_policy_xml):
        """
        Test validation logic rejecting policies exceeding risk thresholds (e.g., LTV > 95%).
        """
        parsed_data = await service.parse_xml_content(high_risk_policy_xml)
        
        with pytest.raises(PolicyValidationError) as exc_info:
            await service.validate_policy_rules(parsed_data)
            
        assert "LTV exceeds maximum limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_policy_record_saves_to_db(self, service, mock_db, valid_policy_xml):
        """
        Test that a successfully parsed policy is persisted to the database.
        """
        parsed_data = await service.parse_xml_content(valid_policy_xml)
        
        result = await service.create_policy_record(parsed_data)
        
        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # Verify the returned object has the expected structure
        assert result.id is not None
        assert result.premium_amount == Decimal("8750.00")

    @pytest.mark.asyncio
    async def test_create_policy_record_rollback_on_error(self, service, mock_db, valid_policy_xml):
        """
        Test that DB transaction rolls back if persistence fails.
        """
        parsed_data = await service.parse_xml_content(valid_policy_xml)
        
        # Simulate DB error during commit
        mock_db.commit.side_effect = Exception("Database connection lost")
        
        with pytest.raises(AppException):
            await service.create_policy_record(parsed_data)
            
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calculate_premium_tier_80_to_85(self, service):
        """
        Test CMHC Premium Tier: 80.01% - 85.00% = 2.80%
        """
        ltv = Decimal("82.50")
        loan_amount = Decimal("100000.00")
        premium = await service.calculate_premium(ltv, loan_amount)
        
        expected = loan_amount * Decimal("0.028")
        assert premium == expected

    @pytest.mark.asyncio
    async def test_calculate_premium_tier_90_to_95(self, service):
        """
        Test CMHC Premium Tier: 90.01% - 95.00% = 4.00%
        """
        ltv = Decimal("92.00")
        loan_amount = Decimal("200000.00")
        premium = await service.calculate_premium(ltv, loan_amount)
        
        expected = loan_amount * Decimal("0.04")
        assert premium == expected

    @pytest.mark.asyncio
    async def test_hashing_of_pii_data(self, service, valid_policy_xml):
        """
        Test that PII (SIN) is hashed before storage/logic.
        """
        # Mock the hashing function to ensure it's called
        with patch("mortgage_underwriting.common.security.hash_pii") as mock_hash:
            mock_hash.return_value = "hashed_sin_123"
            
            await service.parse_xml_content(valid_policy_xml)
            
            # Verify the raw SIN wasn't used directly if logic extracts it
            # (Assuming the service extracts SIN for applicant lookup)
            mock_hash.assert_called()

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from mortgage_underwriting.modules.xml_policy.routes import router
from mortgage_underwriting.common.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture(scope="function")
def app(db_session: AsyncSession):
    """
    Create a test FastAPI app with the XML Policy router.
    Overrides the DB dependency with the test fixture.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policy", tags=["XML Policy"])
    
    # Dependency Override
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestXmlPolicyEndpoints:

    async def test_upload_and_parse_xml_success(self, app: FastAPI, valid_policy_xml):
        """
        Test full workflow: Upload XML -> Parse -> Validate -> Store -> 201 Response
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": valid_policy_xml}
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            
            assert data["policy_id"] == "POL-2023-001"
            assert data["premium"] == "8750.00" # JSON serialization of Decimal
            assert data["insurance_required"] is True
            assert "id" in data
            assert "created_at" in data

    async def test_upload_invalid_xml_returns_400(self, app: FastAPI, invalid_malformed_xml):
        """
        Test that malformed XML returns a structured 400 error.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": invalid_malformed_xml}
            )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            
            assert "detail" in data
            assert "error_code" in data
            assert "XML parsing failed" in data["detail"]

    async def test_upload_validation_error_returns_422(self, app: FastAPI, high_risk_policy_xml):
        """
        Test that business rule violations (e.g., LTV too high) return 422.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": high_risk_policy_xml}
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = response.json()
            
            assert "LTV exceeds maximum limit" in data["detail"]

    async def test_get_policy_by_id(self, app: FastAPI, db_session: AsyncSession, valid_policy_xml):
        """
        Test retrieving a created policy by ID.
        """
        # First, create a policy
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": valid_policy_xml}
            )
            policy_id = create_resp.json()["id"]
            
            # Now retrieve it
            get_resp = await client.get(f"/api/v1/xml-policy/{policy_id}")
            
            assert get_resp.status_code == status.HTTP_200_OK
            data = get_resp.json()
            
            assert data["id"] == policy_id
            assert data["policy_id"] == "POL-2023-001"

    async def test_get_policy_not_found(self, app: FastAPI):
        """
        Test retrieving a non-existent policy returns 404.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/xml-policy/99999")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    async def test_financial_data_integrity_check(self, app: FastAPI, xml_with_float_precision_error):
        """
        Integration test to ensure financial data is stored with Decimal precision
        and not truncated/rounded by the DB or API layer.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": xml_with_float_precision_error}
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            
            # Verify the API returns the exact string representation
            assert data["loan_amount"] == "100000.999"
            assert data["property_value"] == "200000.001"

    async def test_empty_xml_content_rejected(self, app: FastAPI):
        """
        Test that empty or missing XML content is rejected early.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": ""}
            )
            
            # Depending on validation layer, could be 422 (Pydantic) or 400 (Logic)
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]