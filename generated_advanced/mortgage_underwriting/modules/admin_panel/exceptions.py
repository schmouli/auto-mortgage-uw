class AdminPanelException(Exception):
    """Base exception for the Admin Panel module."""
    pass


class InvalidRoleError(AdminPanelException):
    """Raised when an invalid role is provided."""
    pass


class LenderNotFoundError(AdminPanelException):
    """Raised when a lender is not found."""
    pass


class ProductNotFoundError(AdminPanelException):
    """Raised when a product is not found."""
    pass