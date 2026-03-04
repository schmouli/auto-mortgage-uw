```python
# Assuming there's a common.exceptions base file already defined elsewhere in your project
try:
    from ..common.exceptions import BaseCustomException
except ImportError:
    # Fallback if no common base exists
    class BaseCustomException(Exception):
        """Base class for application-specific exceptions."""
        pass


class TestRunNotFoundError(BaseCustomException):
    """Raised when attempting to access a non-existent test run."""
    def __init__(self, message="Test run not found"):
        self.message = message
        super().__init__(self.message)


class TestCaseNotFoundError(BaseCustomException):
    """Raised when attempting to access a non-existent test case."""
    def __init__(self, message="Test case not found"):
        self.message = message
        super().__init__(self.message)


class InvalidTestStatusError(BaseCustomException):
    """Raised when invalid test case status is provided."""
    def __init__(self, message="Invalid test status value"):
        self.message = message
        super().__init__(self.message)


class TestSuiteNotFound(BaseCustomException):
    """Raised when querying stats for a non-existent suite."""
    def __init__(self, message="No test runs found for this suite"):
        self.message = message
        super().__init__(self.message)
```