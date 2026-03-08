"""Common exception classes."""

class ApplicationError(Exception):
    """Base application exception."""
    pass

class ValidationError(ApplicationError):
    """Validation failed."""
    pass

class AuthenticationError(ApplicationError):
    """Authentication failed."""
    pass

class AuthorizationError(ApplicationError):
    """User not authorized."""
    pass

class NotFoundError(ApplicationError):
    """Resource not found."""
    pass
