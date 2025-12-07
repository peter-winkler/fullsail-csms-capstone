"""Formatting utilities for consistent display."""


def format_currency(amount: float, decimals: int = 2) -> str:
    """Format a number as USD currency."""
    return f"${amount:,.{decimals}f}"


def format_duration(hours: float) -> str:
    """Format hours as a readable duration."""
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes} min"
    elif hours < 24:
        return f"{hours:.1f} hrs"
    else:
        days = int(hours // 24)
        remaining_hours = hours % 24
        return f"{days}d {remaining_hours:.1f}h"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a decimal as a percentage."""
    return f"{value * 100:.{decimals}f}%"
