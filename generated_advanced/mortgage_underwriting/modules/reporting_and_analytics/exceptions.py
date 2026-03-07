class ReportingException(Exception):
    """Base exception for reporting module."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class InvalidDateRangeError(ReportingException):
    """Raised when start_date is after end_date."""
    def __init__(self, message: str = "Start date cannot be after end date"):
        super().__init__(message, "REPORTING_001")


class PermissionDeniedError(ReportingException):
    """Raised when user lacks sufficient permissions."""
    def __init__(self, message: str = "Insufficient permissions for reporting"):
        super().__init__(message, "REPORTING_002")


class ValidationError(ReportingException):
    """Raised when input validation fails."""
    def __init__(self, message: str = "Input validation failed"):
        super().__init__(message, "REPORTING_003")