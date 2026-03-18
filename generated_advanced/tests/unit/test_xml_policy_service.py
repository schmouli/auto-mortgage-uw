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