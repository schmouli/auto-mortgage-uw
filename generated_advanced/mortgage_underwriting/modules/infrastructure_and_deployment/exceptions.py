class InfrastructureDeploymentException(Exception):
    """Base exception for infrastructure deployment module."""
    pass


class HealthCheckFailedError(InfrastructureDeploymentException):
    """Raised when a health check fails."""
    error_code = "INFRA_002"
    status_code = 503


class ServiceUnavailableError(InfrastructureDeploymentException):
    """Raised when a service is unavailable."""
    error_code = "INFRA_001"
    status_code = 503


class InvalidConfigurationError(InfrastructureDeploymentException):
    """Raised when system configuration is invalid."""
    error_code = "INFRA_004"
    status_code = 500


class HealthRecordError(InfrastructureDeploymentException):
    """Raised when health record operation fails."""
    error_code = "INFRA_005"
    status_code = 500


class SystemStatusRecordError(InfrastructureDeploymentException):
    """Raised when system status record operation fails."""
    error_code = "INFRA_006"
    status_code = 500


class InvalidInputError(InfrastructureDeploymentException):
    """Raised when input validation fails."""
    error_code = "INFRA_007"
    status_code = 400