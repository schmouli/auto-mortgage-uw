from mortgage_underwriting.common.exceptions import AppException

class TestRunNotFoundError(AppException):
    """Raised when a requested test run cannot be found."""
    pass

class TestRunCreationError(AppException):
    """Raised when there is an error creating a test run record."""
    pass