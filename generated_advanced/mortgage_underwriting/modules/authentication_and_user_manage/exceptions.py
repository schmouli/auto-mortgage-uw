from mortgage_underwriting.common.exceptions import AppException


class AuthException(AppException):
    """Base authentication exception."""
    pass


class InvalidCredentialsException(AuthException):
    """Raised when user provides invalid login credentials."""
    def __init__(self) -> None:
        super().__init__(detail="Invalid credentials", error_code="AUTH_004")


class UserExistsException(AuthException):
    """Raised when trying to register with existing email."""
    def __init__(self) -> None:
        super().__init__(detail="User with this email already exists", error_code="AUTH_003")


class InvalidRefreshTokenException(AuthException):
    """Raised when refresh token is invalid or expired."""
    def __init__(self) -> None:
        super().__init__(detail="Invalid refresh token", error_code="AUTH_005")


class UserNotFoundException(AuthException):
    """Raised when user is not found."""
    def __init__(self) -> None:
        super().__init__(detail="User not found", error_code="AUTH_006")