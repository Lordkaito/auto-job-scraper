"""
display.py
----------
Terminal display helpers shared across scraper and CLI output.
"""


def link(text: str, url: str) -> str:
    """Wraps text in an OSC 8 hyperlink — clickable in most modern terminals."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def file_link(text: str, path) -> str:
    """
    Wraps text in a clickable OSC 8 hyperlink pointing to a local file or folder.
    Accepts a str or pathlib.Path. Uses Path.as_uri() for correct cross-platform
    file:// URLs (handles Windows drive letters, spaces, etc.).
    """
    from pathlib import Path
    uri = Path(path).as_uri()
    return link(text, uri)


def bar(value: float, max_value: float = 10.0, width: int = 10) -> str:
    """Returns a filled/empty block progress bar, e.g. ████████░░ for 8/10."""
    filled = round((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def score_label(score: float) -> str:
    """Returns a short quality label for a final score."""
    if score >= 8.0:
        return "GREAT"
    elif score >= 6.5:
        return "GOOD"
    elif score >= 5.0:
        return "OK"
    else:
        return "LOW"
