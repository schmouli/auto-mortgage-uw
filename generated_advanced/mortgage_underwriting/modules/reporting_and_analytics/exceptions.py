from mortgage_underwriting.common.exceptions import AppException


class ReportingError(AppException):
    """Base exception for reporting module."""
    pass


class MetricsFetchError(ReportingError):
    """Raised when fetching metrics fails."""
    pass


class ExportError(ReportingError):
    """Raised when exporting data fails."""
    pass