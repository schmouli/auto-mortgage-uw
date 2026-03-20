class FrontendUIError(Exception):
    """Base exception for frontend UI module errors."""
    pass


class ModuleNotFoundError(FrontendUIError):
    """Raised when a requested UI module is not found."""
    pass


class ComponentNotFoundError(FrontendUIError):
    """Raised when a requested UI component is not found."""
    pass