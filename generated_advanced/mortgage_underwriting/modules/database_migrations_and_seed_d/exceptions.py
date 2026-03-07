class MigrationException(Exception):
    """Base exception for migration-related errors."""
    pass

class SeedExecutionException(MigrationException):
    """Raised when seed execution fails."""
    pass

class InvalidRevisionException(MigrationException):
    """Raised when an invalid migration revision is detected."""
    pass