class TestManagementError(Exception):
    """Base exception for test management operations."""
    pass


class TestScenarioNotFoundError(TestManagementError):
    """Raised when a test scenario is not found."""
    pass


class TestExecutionNotFoundError(TestManagementError):
    """Raised when a test execution is not found."""
    pass


class TestFixtureNotFoundError(TestManagementError):
    """Raised when a test fixture is not found."""
    pass


class TestExecutionFailedError(TestManagementError):
    """Raised when a test execution fails."""
    pass


class TestFixtureDecryptError(TestManagementError):
    """Raised when decryption of test fixture data fails."""
    pass