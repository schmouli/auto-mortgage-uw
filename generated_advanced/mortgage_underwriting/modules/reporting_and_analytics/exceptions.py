from mortgage_underwriting.common.exceptions import AppException


class ReportingError(AppException):
    """Base exception for reporting module."""
    pass


class InvalidDateRangeError(ReportingError):
    """Raised when start_date is after end_date."""
    error_code = "REPORTING_002"
    status_code = 422


class UnsupportedPeriodError(ReportingError):
    """Raised when an unsupported period type is requested."""
    error_code = "REPORTING_003"
    status_code = 400


class ExportGenerationError(ReportingError):
    """Raised when report export fails."""
    error_code = "REPORTING_004"
    status_code = 500