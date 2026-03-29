class DecisionEngineError(Exception):
    """Base exception for decision engine errors."""
    pass


class InvalidInputError(DecisionEngineError):
    """Raised when input data fails validation."""
    pass


class CalculationError(DecisionEngineError):
    """Raised when financial calculations fail."""
    pass


class ComplianceViolationError(DecisionEngineError):
    """Raised when regulatory compliance check fails."""
    pass