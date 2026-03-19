from mortgage_underwriting.common.exceptions import AppException


class JobNotFoundException(AppException):
    """Raised when a requested job is not found."""
    def __init__(self, message: str = "Job not found", error_code: str = "JOB_001"):
        super().__init__(message, error_code)


class JobDisabledException(AppException):
    """Raised when attempting to trigger a disabled job."""
    def __init__(self, message: str = "Job is disabled", error_code: str = "JOB_002"):
        super().__init__(message, error_code)


class JobExecutionFailedException(AppException):
    """Raised when a job execution fails."""
    def __init__(self, message: str = "Job execution failed", error_code: str = "JOB_003"):
        super().__init__(message, error_code)


class InvalidJobNameException(AppException):
    """Raised when job name is invalid or empty."""
    # FIXED: Added missing exception class for input validation
    def __init__(self, message: str = "Invalid job name", error_code: str = "JOB_004"):
        super().__init__(message, error_code)


class InvalidStatusException(AppException):
    """Raised when job execution status is invalid."""
    # FIXED: Added missing exception class for status validation
    def __init__(self, message: str = "Invalid job execution status", error_code: str = "JOB_005"):
        super().__init__(message, error_code)