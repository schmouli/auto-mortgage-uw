```
from mortgage_underwriting.common.exceptions import AppException

class UserNotFoundError(AppException):
    """Raised when a user is not found in the system"""
    def __init__(self, message: str = "User not found"):
        super().__init__(message, "USER_NOT_FOUND")

class LenderNotFoundError(AppException):
    """Raised when a lender is not found in the system"""
    def __init__(self, message: str = "Lender not found"):
        super().__init__(message, "LENDER_NOT_FOUND")

class ProductNotFoundError(AppException):
    """Raised when a product is not found in the system"""
    def __init__(self, message: str = "Product not found"):
        super().__init__(message, "PRODUCT_NOT_FOUND")

class ApplicationNotFoundError(AppException):
    """Raised when an application is not found in the system"""
    def __init__(self, message: str = "Application not found"):
        super().__init__(message, "APPLICATION_NOT_FOUND")

class DocumentNotFoundError(AppException):
    """Raised when a document is not found in the system"""
    def __init__(self, message: str = "Document not found"):
        super().__init__(message, "DOCUMENT_NOT_FOUND")

class InvalidCredentialsError(AppException):
    """Raised when user credentials are invalid"""
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, "INVALID_CREDENTIALS")

class PermissionDeniedError(AppException):
    """Raised when user lacks permission for an action"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, "PERMISSION_DENIED")
```