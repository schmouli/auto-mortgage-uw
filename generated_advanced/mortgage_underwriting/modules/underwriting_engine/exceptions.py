class ApplicationNotFoundError(Exception):
    """Raised when an underwriting application cannot be found"""
    pass


class InvalidOverrideError(Exception):
    """Raised when an override request is invalid"""
    pass


class UnderwritingCalculationError(Exception):
    """Raised when there's an error in underwriting calculations"""
    pass
```