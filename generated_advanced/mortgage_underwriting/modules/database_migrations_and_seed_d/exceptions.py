class MigrationError(Exception):
    """Base exception for migration-related errors."""
    pass

class SeedExecutionError(MigrationError):
    """Raised when seed execution fails."""
    pass

class InvalidEnvironmentError(MigrationError):
    """Raised when invalid environment specified for seeding."""
    pass