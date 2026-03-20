class DecisionServiceError(Exception):
    """Base exception for decision service errors."""
    pass


class DecisionNotFoundError(DecisionServiceError):
    """Raised when a decision cannot be found."""
    pass


class EvaluationFailedError(DecisionServiceError):
    """Raised when decision evaluation process fails."""
    pass