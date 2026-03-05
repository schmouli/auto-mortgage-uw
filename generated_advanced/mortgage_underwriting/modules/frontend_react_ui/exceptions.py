from mortgage_underwriting.common.exceptions import AppException


class ComplianceException(AppException):
    """Raised when compliance requirements are not met"""
    pass


class InsuranceException(AppException):
    """Raised when insurance calculation fails"""
    pass


class RatioCalculationException(AppException):
    """Raised when GDS/TDS ratio calculation fails"""
    pass