class AdminPanelException(Exception):
    """Base exception for Admin Panel module."""
    def __init__(self, detail: str, error_code: str):
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class UserNotFoundException(AdminPanelException):
    """Raised when a user is not found."""
    def __init__(self, detail: str = "User not found", error_code: str = "ADMIN_001"):
        super().__init__(detail, error_code)


class LenderNotFoundException(AdminPanelException):
    """Raised when a lender is not found."""
    def __init__(self, detail: str = "Lender not found", error_code: str = "ADMIN_002"):
        super().__init__(detail, error_code)


class ProductNotFoundException(AdminPanelException):
    """Raised when a product is not found."""
    def __init__(self, detail: str = "Product not found", error_code: str = "ADMIN_003"):
        super().__init__(detail, error_code)


class UnauthorizedActionException(AdminPanelException):
    """Raised when an unauthorized action is attempted."""
    def __init__(self, detail: str = "Unauthorized action", error_code: str = "ADMIN_004"):
        super().__init__(detail, error_code)


class InvalidStateException(AdminPanelException):
    """Raised when an operation is attempted in an invalid state."""
    def __init__(self, detail: str = "Invalid state for this operation", error_code: str = "ADMIN_005"):
        super().__init__(detail, error_code)