"""Shared helpers for ReportLab PDF endpoints (prescriptions, billing receipts).

All user-controlled strings interpolated into Paragraph markup must be
XML-escaped with ``xml.sax.saxutils.escape`` (imported directly at each
call site — it is already the shared escape helper) to prevent markup
injection via ReportLab's paragraph parser.
"""


def fmt_date(value) -> str:
    """Format a date or datetime to a readable Indian locale string."""
    if value is None:
        return "—"
    if hasattr(value, "date"):
        value = value.date()
    return value.strftime("%d %B %Y")
