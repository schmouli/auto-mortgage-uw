class XmlPolicyServiceError(Exception):
    """Base exception for XML Policy Service."""
    pass


class XmlParsingError(XmlPolicyServiceError):
    """Raised when XML parsing fails."""
    pass


class PolicyEvaluationError(XmlPolicyServiceError):
    """Raised when policy evaluation fails."""
    pass


class PolicyNotFoundError(XmlPolicyServiceError):
    """Raised when a requested policy is not found."""
    pass