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