class ReportingException(Exception):
    """Base exception for reporting module."""
    def __init__(self, message: str, error_code: str) -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class InvalidDateRangeError(ReportingException):
    """Raised when date range filters are invalid."""
    def __init__(self, message: str = "Invalid date range provided") -> None:
        super().__init__(message, "REPORTING_001")


class UnauthorizedAccessError(ReportingException):
    """Raised when user lacks permissions to access report."""
    def __init__(self, message: str = "User lacks required permissions") -> None:
        super().__init__(message, "REPORTING_003")


class ReportGenerationError(ReportingException):
    """Raised when report generation fails."""
    def __init__(self, message: str = "Failed to generate report") -> None:
        super().__init__(message, "REPORTING_005")


class DataExportError(ReportingException):
    """Raised when data export fails."""
    def __init__(self, message: str = "Failed to export data") -> None:
        super().__init__(message, "REPORTING_009")