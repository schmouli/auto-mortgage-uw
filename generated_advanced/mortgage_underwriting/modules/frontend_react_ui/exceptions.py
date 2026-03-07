from mortgage_underwriting.common.exceptions import AppException

class UiComponentNotFoundError(AppException):
    """Raised when a requested UI component is not found."""
    pass

class UiPageNotFoundError(AppException):
    """Raised when a requested UI page is not found."""
    pass

class InvalidRoutePathError(AppException):
    """Raised when a route path does not conform to expected format."""
    pass