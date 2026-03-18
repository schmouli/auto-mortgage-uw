from mortgage_underwriting.common.exceptions import AppException


class AdminPanelException(AppException):
    """Base exception for Admin Panel module."""
    pass


class UserNotFoundException(AdminPanelException):
    """Raised when a user is not found."""
    def __init__(self, detail: str = "User not found", error_code: str = "ADMIN_003"):
        super().__init__(detail=detail, error_code=error_code)


class LenderNotFoundException(AdminPanelException):
    """Raised when a lender is not found."""
    def __init__(self, detail: str = "Lender not found", error_code: str = "ADMIN_004"):
        super().__init__(detail=detail, error_code=error_code)


class ProductNotFoundException(AdminPanelException):
    """Raised when a product is not found."""
    def __init__(self, detail: str = "Product not found", error_code: str = "ADMIN_005"):
        super().__init__(detail=detail, error_code=error_code)


class InsufficientPrivilegesException(AdminPanelException):
    """Raised when user lacks required privileges."""
    def __init__(self, detail: str = "Insufficient privileges", error_code: str = "ADMIN_006"):
        super().__init__(detail=detail, error_code=error_code)


class InvalidRoleException(AdminPanelException):
    """Raised when attempting to assign an invalid role."""
    def __init__(self, detail: str = "Invalid role specified", error_code: str = "ADMIN_007"):
        super().__init__(detail=detail, error_code=error_code)