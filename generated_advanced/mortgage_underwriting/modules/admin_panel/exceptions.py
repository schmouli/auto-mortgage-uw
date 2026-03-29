class AdminException(Exception):
    """Base exception for admin panel operations."""
    pass


class AdminUserNotFoundError(AdminException):
    """Raised when trying to operate on a non-existent user."""
    pass


class AdminBusinessRuleError(AdminException):
    """Raised when business rule validation fails."""
    pass


class AdminPermissionError(AdminException):
    """Raised when admin lacks permission for an operation."""
    pass