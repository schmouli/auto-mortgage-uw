from mortgage_underwriting.common.exceptions import AppException


class InfrastructureException(AppException):
    """Base exception for infrastructure-related errors."""
    pass


class HealthCheckFailedError(InfrastructureException):
    """Raised when health checks fail critically."""
    error_code = "INFRA_001"
    status_code = 503


class DeploymentNotFoundError(InfrastructureException):
    """Raised when requested deployment does not exist."""
    error_code = "DEPLOYMENT_NOT_FOUND"
    status_code = 404


class RollbackNotAllowedError(InfrastructureException):
    """Raised when rollback is requested for non-failed deployment."""
    error_code = "ROLLBACK_NOT_ALLOWED"
    status_code = 400