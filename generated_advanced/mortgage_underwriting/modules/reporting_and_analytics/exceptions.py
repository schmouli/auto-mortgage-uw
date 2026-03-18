from mortgage_underwriting.common.exceptions import AppException


class ReportingException(AppException):
    """Base exception for Reporting & Analytics module."""
    pass


class InvalidDateRangeError(ReportingException):
    """Raised when start_date is after end_date."""
    def __init__(self) -> None:
        super().__init__(
            detail="Invalid date range: start_date must be before or equal to end_date",
            error_code="REPORTING_001"
        )


class InsufficientPermissionsError(ReportingException):
    """Raised when user lacks permission to access reports."""
    def __init__(self) -> None:
        super().__init__(
            detail="Insufficient permissions to access reporting metrics",
            error_code="REPORTING_002"
        )


class InvalidLenderIdError(ReportingException):
    """Raised when lender_id is not a positive integer."""
    def __init__(self) -> None:
        super().__init__(
            detail="lender_id must be a positive integer",
            error_code="REPORTING_003"
        )


class InvalidDateFormatError(ReportingException):
    """Raised when date format is incorrect."""
    def __init__(self) -> None:
        super().__init__(
            detail="Invalid date format. Expected YYYY-MM-DD.",
            error_code="REPORTING_004"
        )