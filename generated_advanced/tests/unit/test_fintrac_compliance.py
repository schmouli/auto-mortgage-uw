```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from onlendhub.modules.fintrac import service # Assumed module path
from onlendhub.modules.fintrac.exceptions import ComplianceError, DocumentExpiredError

# Unit Tests for FINTRAC Compliance Service Layer
# Focus: Business Logic, External API Mocking, Validation Rules

class TestIdentityVerification:

    def test_validate_passport_success(self, valid_individual_payload):
        """Test happy path for valid passport validation."""
        # Arrange
        doc_data = valid_individual_payload['id_document']
        
        # Act
        result = service.validate_identity_document(doc_data)
        
        # Assert
        assert result['is_valid'] is True
        assert result['document_type'] == 'PASSPORT'
        assert 'expiry_date' in result

    def test_validate_expired_document(self, valid_individual_payload):
        """Test that an expired document raises an error."""
        # Arrange
        past_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        valid_individual_payload['id_document']['expiry_date'] = past_date
        
        # Act & Assert
        with pytest.raises(DocumentExpiredError) as exc_info:
            service.validate_identity_document(valid_individual_payload['id_document'])
        
        assert "expired" in str(exc_info.value).lower()

    def test_validate_missing_id_number(self, valid_individual_payload):
        """Test validation failure when ID number is missing."""
        # Arrange
        valid_individual_payload['id_document']['number'] = ""
        
        # Act
        result = service.validate_identity_document(valid_individual_payload['id_document'])
        
        # Assert
        assert result['is_valid'] is False
        assert 'missing_field' in result['errors']

    def test_corporate_registration_validation(self, valid_corp_payload):
        """Test corporate registration number format."""
        # Act
        result = service.validate_corporate_entity(valid_corp_payload)
        
        # Assert
        assert result['is_valid'] is True
        assert result['jurisdiction'] == 'Ontario'

    def test_corporate_registration_invalid_length(self, valid_corp_payload):
        """Test that short registration numbers fail."""
        # Arrange
        valid_corp_payload['registration_number'] = "123"
        
        # Act
        result = service.validate_corporate_entity(valid_corp_payload)
        
        # Assert
        assert result['is_valid'] is False


class TestPEPScreening:

    @patch('onlendhub.modules.fintrac.service.requests.get')
    def test_check_pep_status_match_found(self, mock_get, pep_watchlist_mock):
        """Test external API call handling when PEP is found."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = pep_watchlist_mock
        mock_get.return_value = mock_response
        
        full_name = "John Doe"
        
        # Act
        result = service.screen_pep_and_sanctions(full_name)
        
        # Assert
        assert result['is_pep'] is True
        assert result['risk_level'] == 'HIGH'
        mock_get.assert_called_once()

    @patch('onlendhub.modules.fintrac.service.requests.get')
    def test_check_pep_status_clean(self, mock_get, clean_watchlist_mock):
        """Test external API call handling when client is clean."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = clean_watchlist_mock
        mock_get.return_value = mock_response
        
        full_name = "Jane Smith"
        
        # Act
        result = service.screen_pep_and_sanctions(full_name)
        
        # Assert
        assert result['is_pep'] is False
        assert result['risk_level'] == 'LOW'

    @patch('onlendhub.modules.fintrac.service.requests.get')
    def test_pep_api_timeout_handling(self, mock_get):
        """Test resilience when external watchlist API times out."""
        # Arrange
        mock_get.side_effect = Exception("Connection Timeout")
        
        # Act & Assert
        with pytest.raises(ComplianceError) as exc_info:
            service.screen_pep_and_sanctions("Bad Name")
        
        assert "external service unavailable" in str(exc_info.value).lower()


class TestTransactionThresholds:

    def test_large_cash_threshold_trigger(self):
        """Test that amounts >= $10,000 CAD trigger LCTR logic."""
        # Arrange
        amount_cad = 10000.00
        transaction_type = "CASH_DEPOSIT"
        
        # Act
        report_required = service.check_large_cash_threshold(amount_cad, transaction_type)
        
        # Assert
        assert report_required is True

    def test_large_cash_threshold_below_limit(self):
        """Test that amounts < $10,000 CAD do not trigger LCTR logic."""
        # Arrange
        amount_cad = 9999.99
        transaction_type = "CASH_DEPOSIT"
        
        # Act
        report_required = service.check_large_cash_threshold(amount_cad, transaction_type)
        
        # Assert
        assert report_required is False

    def test_non_cash_transaction_exemption(self):
        """Test that non-cash transactions (e.g., Wire) are exempt from LCTR."""
        # Arrange
        amount_cad = 15000.00
        transaction_type = "WIRE_TRANSFER"
        
        # Act
        report_required = service.check_large_cash_threshold(amount_cad, transaction_type)
        
        # Assert
        assert report_required is False

    def test_structuring_detection(self):
        """Test logic to detect structuring (splitting transactions)."""
        # Arrange
        transactions = [
            {"amount": 5000.00, "date": "2023-01-01"},
            {"amount": 5000.01, "date": "2023-01-01"},
            {"amount": 2000.00, "date": "2023-01-02"}
        ]
        
        # Act
        is_structuring = service.detect_structuring(transactions, threshold_window_days=1)
        
        # Assert
        assert is_structuring is True

    def test_suspicious_activity_flags(self):
        """Test various flags for suspicious activity."""
        # Arrange
        flags = ["client_nervous", "refuses_id", "unusual_source_of_funds"]
        
        # Act
        risk_score = service.calculate_suspicion_score(flags)
        
        # Assert
        assert risk_score > 50 # Assuming a threshold
        assert risk_score == 75 # 3 flags * 25 points each (example logic)


class TestReportGeneration:

    def test_generate_lctr_object(self):
        """Test creation of a Large Cash Transaction Report object."""
        # Arrange
        data = {
            "reporting_entity_id": "12345",
            "amount": 12000.00,
            "currency": "CAD",
            "date": "2023-10-27"
        }
        
        # Act
        lctr = service.create_lctr_report(data)
        
        # Assert
        assert lctr['report_type'] == 'LCTR'
        assert lctr['amount'] == 12000.00
        assert lctr['signature_block'] is not None

    def test_generate_str_object(self):
        """Test creation of a Suspicious Transaction Report object."""
        # Arrange
        data = {
            "suspicion_reasons": ["Unexplained wealth", "Shell company"],
            "filing_date": datetime.now().date()
        }
        
        # Act
        str_report = service.create_str_report(data)
        
        # Assert
        assert str_report['report_type'] == 'STR'
        assert len(str_report['suspicion_reasons']) == 2
        assert 'narrative' in str_report
```