import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# Import paths strictly following project conventions
from mortgage_underwriting.modules.xml_policy.services import XmlPolicyService
from mortgage_underwriting.modules.xml_policy.exceptions import (
    XmlPolicyValidationError,
    XmlPolicyStorageError
)
from mortgage_underwriting.modules.xml_policy.schemas import XmlPolicyCreate, XmlPolicyResponse

@pytest.mark.unit
class TestXmlPolicyService:

    @pytest.fixture
    def mock_db_session(self):
        """Mock AsyncSession for unit tests."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock()
        session.scalars = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        """Fixture for the service instance."""
        return XmlPolicyService(mock_db_session)

    @pytest.mark.asyncio
    async def test_parse_xml_success(self, service, valid_policy_xml):
        """Test that valid XML is parsed correctly into a dictionary."""
        result = await service._parse_xml_content(valid_policy_xml)
        
        assert result is not None
        assert "policy" in result or "meta" in result # Depending on implementation detail
        # Assuming parser extracts root or specific tags
        assert "Standard Residential Policy" in str(result)

    @pytest.mark.asyncio
    async def test_parse_xml_malformed_raises_error(self, service, malformed_policy_xml):
        """Test that malformed XML raises a validation error."""
        with pytest.raises(XmlPolicyValidationError) as exc_info:
            await service._parse_xml_content(malformed_policy_xml)
        
        assert "Invalid XML format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_policy_structure_success(self, service, valid_policy_xml):
        """Test business logic validation of required XML nodes."""
        parsed_data = await service._parse_xml_content(valid_policy_xml)
        # Should not raise
        await service._validate_policy_rules(parsed_data)

    @pytest.mark.asyncio
    async def test_validate_policy_structure_missing_fields(self, service, policy_schema_violation_xml):
        """Test validation fails if critical fields (like version) are missing."""
        parsed_data = await service._parse_xml_content(policy_schema_violation_xml)
        
        with pytest.raises(XmlPolicyValidationError) as exc_info:
            await service._validate_policy_rules(parsed_data)
        
        assert "Missing required field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_policy_success(self, service, mock_db_session, valid_policy_xml):
        """Test successful creation of a policy record."""
        payload = XmlPolicyCreate(
            name="Test Policy",
            version="1.0.0",
            content=valid_policy_xml
        )
        
        # Mock the return of the model instance after refresh
        mock_model_instance = MagicMock()
        mock_model_instance.id = 1
        mock_model_instance.created_at = datetime.utcnow()
        mock_model_instance.name = payload.name
        
        # Setup refresh to return the mock object
        async def mock_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.utcnow()
            
        mock_db_session.refresh.side_effect = mock_refresh

        result = await service.create_policy(payload)
        
        assert isinstance(result, XmlPolicyResponse)
        assert result.name == "Test Policy"
        assert result.id == 1
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_policy_db_failure(self, service, mock_db_session, valid_policy_xml):
        """Test handling of database errors during creation."""
        payload = XmlPolicyCreate(
            name="Failing Policy",
            version="1.0.0",
            content=valid_policy_xml
        )
        
        # Simulate a database constraint error
        mock_db_session.commit.side_effect = SQLAlchemyError("DB Connection Failed")
        
        with pytest.raises(XmlPolicyStorageError) as exc_info:
            await service.create_policy(payload)
        
        assert "Failed to store policy" in str(exc_info.value)
        mock_db_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_policy_by_id_success(self, service, mock_db_session, valid_policy_xml):
        """Test retrieving a policy by ID."""
        policy_id = 1
        
        # Mock the database response
        mock_policy = MagicMock()
        mock_policy.id = policy_id
        mock_policy.name = "Retrieved Policy"
        mock_policy.content = valid_policy_xml
        mock_policy.created_at = datetime.utcnow()
        
        mock_result = MagicMock()
        mock_result.unique.return_value = MagicMock()
        mock_result.unique.return_value.first.return_value = mock_policy
        
        # Execute mock chain: execute -> scalars -> unique -> first
        mock_db_session.execute.return_value = mock_result
        
        result = await service.get_policy_by_id(policy_id)
        
        assert result is not None
        assert result.id == policy_id
        assert result.name == "Retrieved Policy"
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_policy_by_id_not_found(self, service, mock_db_session):
        """Test retrieving a non-existent policy returns None."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.unique.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await service.get_policy_by_id(999)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_ingest_and_parse_full_workflow(self, service, valid_policy_xml):
        """Test the high-level workflow of ingest, parse, and validate."""
        # This simulates the service method that ties parsing and validation together
        # before saving.
        
        parsed = await service._parse_xml_content(valid_policy_xml)
        await service._validate_policy_rules(parsed)
        
        # If we get here, no exceptions were raised
        assert True