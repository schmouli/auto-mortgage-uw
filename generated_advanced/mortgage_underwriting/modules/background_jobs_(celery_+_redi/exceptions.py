from mortgage_underwriting.common.exceptions import AppException

class JobNotFoundError(AppException):
    """Raised when a requested job is not found."""
    pass

class InvalidTaskNameError(AppException):
    """Raised when an invalid task name is provided."""
    pass