from mortgage_underwriting.common.exceptions import AppException


class FintracComplianceError(AppException):
    """Base exception for FINTRAC compliance module"""
    pass


class VerificationNotFoundError(FintracComplianceError):
    """Raised when a verification record cannot be found"""
    pass


class InvalidAmountError(FintracComplianceError):
    """Raised when a transaction amount is invalid"""
    pass


class ReportSubmissionError(FintracComplianceError):
    """Raised when there's an error submitting a transaction report"""
    pass


class RiskAssessmentError(FintracComplianceError):
    """Raised when there's an error generating a risk assessment"""
    pass
```