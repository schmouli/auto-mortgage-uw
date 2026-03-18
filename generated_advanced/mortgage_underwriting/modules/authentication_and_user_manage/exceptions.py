from mortgage_underwriting.common.exceptions import AppException


class AuthException(AppException):
    """Base authentication exception."""
    pass


class InvalidCredentialsException(AuthException):
    """Raised when login credentials are invalid."""
    def __init__(self) -> None:
        super().__init__(
            detail="Invalid credentials",
            error_code="AUTH_004"
        )


class UserAlreadyExistsException(AuthException):
    """Raised when trying to register with existing email."""
    def __init__(self) -> None:
        super().__init__(
            detail="Email already registered",
            error_code="AUTH_001"
        )


class InvalidRefreshTokenException(AuthException):
    """Raised when refresh token is invalid/expired/revoked."""
    def __init__(self) -> None:
        super().__init__(
            detail="Invalid refresh token",
            error_code="AUTH_005"
        )


class UserNotFoundException(AuthException):
    """Raised when user not found."""
    def __init__(self) -> None:
        super().__init__(
            detail="User not found",
            error_code="AUTH_006"
        )