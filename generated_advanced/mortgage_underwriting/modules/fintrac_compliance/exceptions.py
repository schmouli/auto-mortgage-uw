```python
from app.exceptions.base import CustomException


class FintracComplianceError(CustomException):
    """Base exception for FINTRAC compliance errors"""
    pass


class VerificationNotFoundError(FintracComplianceError):
    """Raised when a verification record cannot be found"""
    def __init__(self, message: str = "Verification record not found"):
        self.message = message
        super().__init__(self.message)


class InvalidAmountError(FintracComplianceError):
    """Raised when a transaction amount is invalid"""
    def __init__(self, message: str = "Invalid transaction amount"):
        self.message = message
        super().__init__(self.message)


class StructuringDetectionError(FintracComplianceError):
    """Raised when there's an error detecting structuring patterns"""
    def __init__(self, message: str = "Error in structuring detection process"):
        self.message = message
        super().__init__(self.message)


class ReportSubmissionError(FintracComplianceError):
    """Raised when there's an error submitting a report to FINTRAC"""
    def __init__(self, message: str = "Error submitting report to FINTRAC"):
        self.message = message
        super().__init__(self.message)
```