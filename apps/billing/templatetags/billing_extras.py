from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def div(value, arg):
    """
    Divide the value by the argument
    Usage: {{ value|div:arg }}
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """
    Multiply the value by the argument
    Usage: {{ value|mul:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """
    Alias for mul filter
    Usage: {{ value|multiply:arg }}
    """
    return mul(value, arg)

@register.filter
def sub(value, arg):
    """
    Subtract argument from value
    Usage: {{ value|sub:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """
    Add argument to value
    Usage: {{ value|add:arg }}
    """
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """
    Calculate percentage
    Usage: {{ value|percentage:total }}
    """
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def months_covered(credit_amount, monthly_rate):
    """
    Calculate months covered by credit
    Usage: {{ credit_amount|months_covered:monthly_rate }}
    """
    try:
        return (Decimal(str(credit_amount)) / Decimal(str(monthly_rate))).quantize(Decimal('0.01'))
    except (ValueError, ZeroDivisionError, TypeError):
        return Decimal('0.00')