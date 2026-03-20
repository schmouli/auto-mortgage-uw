class ApplicationError(Exception):
    """Base exception for application module."""
    pass


class InvalidApplicationDataError(ApplicationError):
    """Raised when application data fails validation."""
    pass


class ApplicationNotSubmittableError(ApplicationError):
    """Raised when trying to submit an application that is not in a submittable state."""
    pass