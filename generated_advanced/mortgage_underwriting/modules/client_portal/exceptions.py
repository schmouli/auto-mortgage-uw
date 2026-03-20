from mortgage_underwriting.common.exceptions import AppException

class PortalException(AppException):
    """Base exception for Client Portal module."""
    pass

class NotificationNotFoundError(PortalException):
    """Raised when a notification is not found."""
    def __init__(self, detail: str = "Notification not found", error_code: str = "NOTIFICATION_001"):
        super().__init__(detail=detail, error_code=error_code)

class AccessDeniedError(PortalException):
    """Raised when access to a resource is denied."""
    def __init__(self, detail: str = "Access denied", error_code: str = "PORTAL_001"):
        super().__init__(detail=detail, error_code=error_code)