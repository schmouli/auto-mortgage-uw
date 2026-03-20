class TestingSuiteException(Exception):
    """Base exception for Testing Suite module."""
    pass


class TestRunCreationError(TestingSuiteException):
    """Raised when test run creation fails."""
    pass


class TestRunUpdateError(TestingSuiteException):
    """Raised when test run update fails."""
    pass


class TestRunNotFoundError(TestingSuiteException):
    """Raised when requested test run does not exist."""
    pass


class TestCaseCreationError(TestingSuiteException):
    """Raised when test case creation fails."""
    pass


class TestCaseUpdateError(TestingSuiteException):
    """Raised when test case update fails."""
    pass


class TestCaseNotFoundError(TestingSuiteException):
    """Raised when requested test case does not exist."""
    pass


class CoverageReportCreationError(TestingSuiteException):
    """Raised when coverage report creation fails."""
    pass


class CoverageReportUpdateError(TestingSuiteException):
    """Raised when coverage report update fails."""
    pass


class CoverageReportNotFoundError(TestingSuiteException):
    """Raised when requested coverage report does not exist."""
    pass