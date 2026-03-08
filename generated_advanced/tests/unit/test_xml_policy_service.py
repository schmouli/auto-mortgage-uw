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