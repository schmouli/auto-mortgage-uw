from mortgage_underwriting.common.exceptions import AppException


class AuthException(AppException):
    """Base authentication exception."""
    pass


class InvalidCredentialsException(AuthException):
    """Raised when provided credentials are invalid."""
    def __init__(self) -> None:
        super().__init__("Invalid credentials provided", "INVALID_CREDENTIALS")


class UserAlreadyExistsException(AuthException):
    """Raised when attempting to register with an existing email."""
    def __init__(self) -> None:
        super().__init__("User with this email already exists", "USER_EXISTS")


class InvalidTokenException(AuthException):
    """Raised when refresh token is invalid or expired."""
    def __init__(self) -> None:
        super().__init__("Invalid or expired refresh token", "INVALID_REFRESH_TOKEN")


class UserNotFoundException(AuthException):
    """Raised when user is not found."""
    def __init__(self) -> None:
        super().__init__("User not found", "USER_NOT_FOUND")