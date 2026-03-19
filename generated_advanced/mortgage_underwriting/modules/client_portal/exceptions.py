class ClientPortalException(Exception):
    """Base exception for Client Portal module."""
    pass


class InvalidCredentialsError(ClientPortalException):
    """Raised when login credentials are invalid."""
    pass


class AccountLockedError(ClientPortalException):
    """Raised when account is temporarily locked due to failed attempts."""
    pass


class TokenExpiredError(ClientPortalException):
    """Raised when JWT token has expired."""
    pass


class InsufficientPermissionsError(ClientPortalException):
    """Raised when user lacks permission to perform action."""
    pass