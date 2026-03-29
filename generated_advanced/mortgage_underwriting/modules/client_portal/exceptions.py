from mortgage_underwriting.common.exceptions import AppException, NotFoundError


class ClientPortalError(AppException):
    """Base exception for Client Portal module."""
    pass


class ClientPortalAuthError(ClientPortalError):
    """Raised when authentication fails."""
    error_code = "CLIENT_PORTAL_002"


class ClientPortalNotFoundError(ClientPortalError):
    """Raised when a requested resource is not found."""
    error_code = "CLIENT_PORTAL_003"


class ClientPortalPermissionError(ClientPortalError):
    """Raised when access is denied to a resource."""
    error_code = "CLIENT_PORTAL_004"


class ClientPortalValidationError(ClientPortalError):
    """Raised when input validation fails."""
    error_code = "CLIENT_PORTAL_007"


class ClientPortalBusinessRuleError(ClientPortalError):
    """Raised when a business rule is violated."""
    error_code = "CLIENT_PORTAL_008"