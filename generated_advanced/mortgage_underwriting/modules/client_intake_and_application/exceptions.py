--- exceptions.py ---
from mortgage_underwriting.common.exceptions import AppException


class ClientIntakeException(AppException):
    """Base exception for client intake module"""
    pass