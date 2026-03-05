from mortgage_underwriting.common.exceptions import AppException


class DeploymentNotFoundError(AppException):
    """Raised when a deployment is not found"""
    pass


class ServiceNotFoundError(AppException):
    """Raised when a service is not found"""
    pass


class ConfigurationNotFoundError(AppException):
    """Raised when a configuration is not found"""
    pass


class InvalidDeploymentNameError(AppException):  # FIXED: Completed the class definition
    """Raised when a deployment name is invalid"""
    pass


class DeploymentCreationError(AppException):
    """Raised when deployment creation fails"""
    pass


class ServiceCreationError(AppException):
    """Raised when service creation fails"""
    pass


class ConfigurationCreationError(AppException):
    """Raised when configuration creation fails"""
    pass
```

```