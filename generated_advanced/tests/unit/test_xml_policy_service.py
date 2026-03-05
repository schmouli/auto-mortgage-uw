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