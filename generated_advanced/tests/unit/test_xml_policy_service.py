```python
import pytest
from unittest.mock import MagicMock, patch
from services.xml_policy_service import XMLPolicyService, PolicyEngine
from exceptions import XMLParsingError, ValidationError, PolicyViolationError
from models import MortgageApplication

# Test XML Parsing Logic
def test_parse_valid_xml_success(valid_mortgage_xml):
    """
    Unit Test: Ensure XML string is correctly parsed into a dictionary.
    Assertions: Check parsing success and data integrity.
    """
    service = XMLPolicyService()
    data = service.parse_xml(valid_mortgage_xml)
    
    assert data is not None
    assert data['ApplicationID'] == 'APP-2023-001'
    assert data['Borrower']['FirstName'] == 'John'
    assert data['Loan']['Amount'] == 400000
    assert data['Property']['Province'] == 'ON'

def test_parse_malformed_xml_raises_error(malformed_xml):
    """
    Unit Test: Ensure service handles malformed XML gracefully.
    Assertions: Verify specific exception is raised.
    """
    service = XMLPolicyService()
    with pytest.raises(XMLParsingError):
        service.parse_xml(malformed_xml)

# Test Data Validation
def test_validate_missing_field_raises_error(missing_required_field_xml):
    """
    Unit Test: Ensure validation logic catches missing mandatory fields.
    Assertions: Check that ValidationError is raised for missing CreditScore.
    """
    service = XMLPolicyService()
    parsed_data = service.parse_xml(missing_required_field_xml)
    
    with pytest.raises(ValidationError) as exc_info:
        service.validate_application_data(parsed_data)
    assert "CreditScore" in str(exc_info.value)

def test_validate_ltv_calculation():
    """
    Unit Test: Loan-to-Value (LTV) calculation accuracy.
    Assertions: Verify LTV is calculated correctly (Loan / Property Value).
    """
    engine = PolicyEngine()
    # Loan 400k / Value 500k = 80%
    ltv = engine.calculate_ltv(400000, 500000)
    assert ltv == 80.0
    
    # Edge case: 0 value
    with pytest.raises(ZeroDivisionError):
        engine.calculate_ltv(100000, 0)

# Test Policy Rules (Canadian Context)
def test_policy_approves_good_credit(valid_mortgage_xml):
    """
    Unit Test: Happy path for policy approval.
    Assertions: High credit score + standard LTV = Approved.
    """
    service = XMLPolicyService()
    data = service.parse_xml(valid_mortgage_xml)
    
    # Mock DB save
    with patch.object(service, 'save_to_db', return_value=1):
        result = service.process_application(data)
        
    assert result['status'] == 'Approved'
    assert result['application_id'] == 'APP-2023-001'
    assert 'rate' in result

def test_policy_rejects_low_credit():
    """
    Unit Test: Business rule enforcement for low credit score.
    Assertions: Score < 600 should result in Rejection.
    """
    engine = PolicyEngine()
    application_data = {
        'CreditScore': 550,
        'LTV': 70.0,
        'Province': 'ON'
    }
    
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.evaluate_risk(application_data)
    assert "Credit score too low" in str(exc_info.value)

def test_policy_requires_insurance_high_ltv():
    """
    Unit Test: Canadian mortgage rule (High LTV).
    Assertions: LTV > 80% should trigger 'Insurance Required' status.
    """
    engine = PolicyEngine()
    # Loan 450k / Value 500k = 90%
    application_data = {
        'CreditScore': 700,
        'LTV': 90.0,
        'Province': 'BC'
    }
    
    result = engine.evaluate_risk(application_data)
    assert result['status'] == 'Manual Review' # Or Insurance Required based on logic
    assert 'Insurance' in result['notes']

def test_province_specific_logic():
    """
    Unit Test: Provincial checks (e.g., Quebec or specific restrictions).
    Assertions: Ensure logic handles province codes correctly.
    """
    engine = PolicyEngine()
    # Hypothetical rule: QC requires extra checks
    app_qc = {'Province': 'QC', 'CreditScore': 650, 'LTV': 75.0}
    result = engine.evaluate_risk(app_qc)
    
    assert result['region'] == 'Quebec'

def test_xml_response_generation():
    """
    Unit Test: Verify the service generates correct XML response.
    Assertions: Check XML tags and values in the output string.
    """
    service = XMLPolicyService()
    decision = {
        'status': 'Approved',
        'application_id': 'APP-001',
        'rate': 4.5
    }
    
    response_xml = service.generate_response_xml(decision)
    root = ET.fromstring(response_xml)
    
    assert root.tag == 'Decision'
    assert root.find('Status').text == 'Approved'
    assert root.find('ApplicationID').text == 'APP-001'
    assert float(root.find('OfferedRate').text) == 4.5

# Test External Dependencies
@patch('services.xml_policy_service.CreditBureauClient')
def test_external_credit_check_called(mock_bureau, valid_mortgage_xml):
    """
    Unit Test: Verify external API interaction.
    Assertions: Ensure CreditBureauClient is called with correct SIN/ID.
    """
    mock_bureau.return_value.get_score.return_value = 720
    service = XMLPolicyService(credit_client=mock_bureau)
    data = service.parse_xml(valid_mortgage_xml)
    
    service.enhance_credit_data(data)
    
    mock_bureau.return_value.get_score.assert_called_once()
    assert data['ExternalCreditScore'] == 720

# Test Error Handling
def test_empty_payload_handling():
    """
    Unit Test: Handling of empty or None inputs.
    Assertions: Service should not crash on empty input, raise error.
    """
    service = XMLPolicyService()
    with pytest.raises(XMLParsingError):
        service.parse_xml("")
        
    with pytest.raises(ValidationError):
        service.validate_application_data(None)

def test_negative_loan_amount_handling():
    """
    Unit Test: Data sanitization.
    Assertions: Negative loan amounts should be caught during validation.
    """
    service = XMLPolicyService()
    data = {
        'Loan': {'Amount': -50000},
        'Property': {'Value': 100000},
        'Borrower': {'CreditScore': 700}
    }
    
    with pytest.raises(ValidationError) as exc_info:
        service.validate_application_data(data)
    assert "positive" in str(exc_info.value).lower()
```