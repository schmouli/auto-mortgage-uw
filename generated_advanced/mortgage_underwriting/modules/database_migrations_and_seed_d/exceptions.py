```python
class BaseMigrationException(Exception):
    """Base exception for migration module"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class UserNotFoundError(BaseMigrationException):
    """Raised when a user is not found"""
    pass

class LenderNotFoundError(BaseMigrationException):
    """Raised when a lender is not found"""
    pass

class ProductNotFoundError(BaseMigrationException):
    """Raised when a product is not found"""
    pass

class ApplicationNotFoundError(BaseMigrationException):
    """Raised when an application is not found"""
    pass

class DocumentNotFoundError(BaseMigrationException):
    """Raised when a document is not found"""
    pass

class SeedingError(BaseMigrationException):
    """Raised when database seeding fails"""
    pass
```