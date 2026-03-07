class AuthException(Exception):
    """Base authentication exception."""
    pass

class InvalidCredentialsError(AuthException):
    """Raised when user provides invalid credentials."""
    pass

class UserAlreadyExistsError(AuthException):
    """Raised when trying to register with an existing email."""
    pass

class RefreshTokenInvalidError(AuthException):
    """Raised when refresh token is invalid or expired."""
    pass

class PasswordValidationError(AuthException):
    """Raised when password does not meet complexity requirements."""
    pass