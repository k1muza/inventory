from django import template

register = template.Library()

@register.filter(name='replace')
def replace(value, args):
    """
    Replaces occurrences of a substring within a string.

    Usage in template:
    {{ value|replace:"old,new" }}
    """
    try:
        old, new = args.split(',', 1)
        return value.replace(old, new)
    except ValueError:
        # If the arguments are not correctly formatted, return the original value
        return value

@register.filter(name='formatquantity')
def formatquantity(value, unit):
    """
    Formats a number as a quantity.

    Usage in template:
    {{ value|formatquantity:"unit" }}
    """
    if unit == 'unit':
        return f"{value:.0f}"
    else:
        return f"{value:.3f}"
