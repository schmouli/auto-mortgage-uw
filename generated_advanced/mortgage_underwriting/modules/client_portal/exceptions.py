from mortgage_underwriting.common.exceptions import AppException


class ClientPortalException(AppException):
    """Base exception for client portal module."""
    pass


class AuthenticationFailed(ClientPortalException):
    """Raised when user authentication fails."""
    def __init__(self, detail: str = "Invalid credentials", error_code: str = "CLIENT_PORTAL_004"):
        super().__init__(detail=detail, error_code=error_code)


class NotificationNotFound(ClientPortalException):
    """Raised when notification is not found."""
    def __init__(self, detail: str = "Notification not found", error_code: str = "CLIENT_PORTAL_001"):
        super().__init__(detail=detail, error_code=error_code)