from django import template

register = template.Library()


@register.filter
def money(cents):
    """12345 -> €123.45"""
    if cents is None:
        return "–"
    return f"€{int(cents) / 100:,.2f}"


@register.filter
def qty(value):
    """5.000 -> 5, 1.250 -> 1.25"""
    s = f"{value:f}".rstrip("0").rstrip(".") if value is not None else ""
    return s or "0"


@register.filter
def hours_minutes(delta):
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 3600}h {total % 3600 // 60:02d}m"


@register.filter
def euros(cents):
    """12345 -> 123.45 (plain number for form fields)"""
    return f"{int(cents or 0) / 100:.2f}"
