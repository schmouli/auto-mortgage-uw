```python
from app.exceptions.base import AppException


class UnderwritingEngineError(AppException):
    """Base exception for underwriting engine errors"""
    pass


class ApplicationNotFoundError(UnderwritingEngineError):
    """Raised when an application is not found"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InvalidOverrideError(UnderwritingEngineError):
    """Raised when an invalid override attempt is made"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class CalculationError(UnderwritingEngineError):
    """Raised when there's an error in underwriting calculations"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
```