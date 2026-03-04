```python
from common.exceptions import BaseCustomException


class BackgroundJobsBaseException(BaseCustomException):
    """Base exception for background jobs module."""
    pass


class JobNotFoundError(BackgroundJobsBaseException):
    """Raised when a requested job cannot be found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class JobExecutionError(BackgroundJobsBaseException):
    """Raised when a job fails during execution."""
    def __init__(self, job_name: str, reason: str):
        self.job_name = job_name
        self.reason = reason
        super().__init__(
            f"Failed to execute job '{job_name}': {reason}",
            status_code=500
        )
```