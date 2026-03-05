"""Exceptions module for Reporting & Analytics.

This module defines custom exceptions specific to the reporting functionality.
"""

from mortgage_underwriting.common.exceptions import AppException


class ReportingException(AppException):
    """Base exception for reporting module."""
    pass


class ReportNotFoundException(ReportingException):
    """Raised when a requested report cannot be found."""
    pass


class ReportCreationFailedException(ReportingException):
    """Raised when report creation fails."""
    pass
```