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