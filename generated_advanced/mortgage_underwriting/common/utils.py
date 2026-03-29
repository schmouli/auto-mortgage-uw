"""Utility functions."""

from decimal import Decimal
from typing import Any

def format_decimal(value: Decimal, places: int = 2) -> str:
    """Format decimal for display."""
    return f"{value:.{places}f}"

def safe_round(value: Decimal, places: int = 2) -> Decimal:
    """Safely round decimal value."""
    if value is None:
        return Decimal("0")
    return Decimal(str(round(value, places)))
