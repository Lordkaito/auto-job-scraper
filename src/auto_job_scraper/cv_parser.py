"""
cv_parser.py
------------
Extracts user profile data from a CV/resume file.
Supports PDF and plain text (.txt / .md).

Extracted fields:
  - name             (heuristic: first short capitalised line)
  - experience_years (explicit phrases or sum of date ranges)
  - skills           (intersection with ALL_KNOWN_SKILLS)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from auto_job_scraper.config import ALL_KNOWN_SKILLS

_CURRENT_YEAR = datetime.now().year


def parse_cv(path: str) -> dict:
    """
    Reads a CV file and returns a dict with:
      name             : str | None
      experience_years : float | None
      skills           : list[str]

    None values mean the field could not be detected — the caller
    (wizard or CLI) should ask the user to fill them in.
    """
    text = _extract_text(path)

    return {
        "name":             _extract_name(text),
        "experience_years": _extract_experience_years(text),
        "skills":           _extract_skills(text),
    }


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CV file not found: {path}")

    suffix = p.suffix.lower()

    if suffix == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(p))
        pages  = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    if suffix in (".txt", ".md", ""):
        return p.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(
        f"Unsupported file type: '{suffix}'. Supported formats: .pdf, .txt, .md"
    )


# ── Name ──────────────────────────────────────────────────────────────────────

def _extract_name(text: str) -> Optional[str]:
    """
    Heuristic: the CV owner's name is usually the first short,
    capitalised line that doesn't look like a URL, email, or section header.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like contact info or section headers
        if any(ch in line for ch in ["@", "://", "linkedin", "github", "+"]):
            continue
        if re.search(r'\d{5}', line):   # postal code
            continue
        words = line.split()
        if 2 <= len(words) <= 5 and line[0].isupper():
            # Looks like a name (2–5 words, starts with capital)
            return line
    return None


# ── Experience years ──────────────────────────────────────────────────────────

def _extract_experience_years(text: str) -> Optional[float]:
    """
    Two-strategy approach (returns the first successful result):

    1. Explicit phrase: "5 years of experience", "3+ years professional experience"
    2. Date ranges: finds "YYYY – YYYY" / "YYYY – Present" patterns,
       merges overlapping ranges, and sums the total duration.
    """
    lower = text.lower()

    # ── Strategy 1: explicit phrase ───────────────────────────────────────────
    for m in re.finditer(
        r'\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience',
        lower,
    ):
        return float(m.group(1))

    # ── Strategy 2: date ranges ───────────────────────────────────────────────
    ranges: list[tuple[int, int]] = []
    present_aliases = {"present", "current", "now", "today"}

    for m in re.finditer(
        r'\b(20\d{2})\s*[-–—]\s*(20\d{2}|present|current|now|today)\b',
        lower,
    ):
        start   = int(m.group(1))
        end_raw = m.group(2).strip()
        end     = _CURRENT_YEAR if end_raw in present_aliases else int(end_raw)

        if 2000 <= start <= _CURRENT_YEAR and start <= end:
            ranges.append((start, end))

    if ranges:
        merged = _merge_ranges(sorted(ranges))
        total  = sum(e - s for s, e in merged)
        return round(float(total), 1)

    return None


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merges overlapping year ranges to avoid double-counting."""
    merged = [ranges[0]]
    for s, e in ranges[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


# ── Skills ────────────────────────────────────────────────────────────────────

def _extract_skills(text: str) -> list[str]:
    """Returns all ALL_KNOWN_SKILLS entries that appear in the CV text."""
    lower = text.lower()
    return sorted(skill for skill in ALL_KNOWN_SKILLS if skill in lower)
