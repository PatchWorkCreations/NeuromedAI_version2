import re

from django import template

register = template.Library()

_HEADING = re.compile(r"^[#*\s]*([A-Za-z&/ ,’'()-]{2,48}?)[:*#\s]*$")


@register.filter
def summary_preview(text: str) -> str:
    """Plain prose from a visit summary: drop section headings and markdown marks."""
    if not text:
        return ""
    lines = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-•*# ").strip()
        if not line:
            continue
        # Short lines with no sentence punctuation are section headings ("Key points").
        if _HEADING.match(raw.strip()) and not line.endswith((".", "!", "?")):
            continue
        lines.append(line.replace("**", ""))
    return " ".join(lines)


@register.filter
def summary_format(text: str):
    """Render a visit summary with its section headings as real headings. Escapes everything."""
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not text:
        return ""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            flush()
            continue
        clean = escape(stripped.lstrip("#").strip().strip("*").strip())
        if _HEADING.match(stripped) and not clean.endswith((".", "!", "?")):
            flush()
            out.append(f"<h3>{clean.rstrip(':')}</h3>")
        elif stripped[:2] in ("- ", "* ", "• "):
            if para:
                flush()
            items.append(escape(stripped[2:].strip().replace("**", "")))
        else:
            if items:
                flush()
            para.append(escape(stripped.replace("**", "")))
    flush()
    return mark_safe("".join(out))
