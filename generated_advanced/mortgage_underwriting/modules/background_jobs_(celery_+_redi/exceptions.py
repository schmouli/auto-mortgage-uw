from mortgage_underwriting.common.exceptions import AppException


class BackgroundJobError(AppException):
    """Base exception for background job operations."""
    pass


class JobNotFoundError(BackgroundJobError):
    """Raised when a job is not found."""
    pass


class JobCreationError(BackgroundJobError):
    """Raised when job creation fails."""
    pass


class JobUpdateError(BackgroundJobError):
    """Raised when job update fails."""
    pass


class JobDeletionError(BackgroundJobError):
    """Raised when job deletion fails."""
    pass


class JobTriggerError(BackgroundJobError):
    """Raised when job triggering fails."""
    pass