class DatabaseMigrationError(Exception):
    """Raised when a database migration operation fails."""
    pass


class SeedDataError(Exception):
    """Raised when seeding data fails."""
    pass


class RollbackTestError(Exception):
    """Raised when rollback testing fails."""
    pass