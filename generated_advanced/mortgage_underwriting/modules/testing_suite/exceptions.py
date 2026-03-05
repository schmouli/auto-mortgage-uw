"""Exceptions for the testing suite module."""

from ..common.exceptions import AppException


class TestSuiteNotFoundError(AppException):
    """Raised when a test suite is not found."""
    pass


class TestRunNotFoundError(AppException):
    """Raised when a test run is not found."""
    pass


class TestCaseNotFoundError(AppException):
    """Raised when a test case is not found."""
    pass
```