"""
scoring.py
----------
All scoring functions and salary/experience parsers.
Each function returns a float in the range 1.0–10.0
(0.0 for remote score when the role is fully on-site).

Scoring functions accept a UserProfile so they work for any user,
not just the one hardcoded during development.
"""

import re
from typing import Optional

from auto_job_scraper.config import (
    ALL_KNOWN_SKILLS,
    KNOWN_COMPANIES,
    LEVEL_KEYWORD_YEARS,
    SOFT_EXPERIENCE_PHRASES,
)
from auto_job_scraper.models import Job
from auto_job_scraper.profile import UserProfile


# ── Salary parser ─────────────────────────────────────────────────────────────

def parse_salary(text: str) -> tuple[Optional[float], Optional[float]]:
    """
    Extracts a salary range from raw text and treats it as USD regardless of currency symbol.
    Returns (min, max) or (None, None) if no salary is found.
    """
    if not text:
        return None, None

    text = text.replace(",", "").replace(" ", "")

    patterns = [
        r'[\$€£]?(\d+)[Kk]?\s*[-–]\s*[\$€£]?(\d+)[Kk]?',
        r'(\d{4,6})\s*[-–]\s*(\d{4,6})',
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo < 1000:
                lo *= 1000
                hi *= 1000
            return lo, hi

    m = re.search(r'[\$€£]?(\d+)[Kk]?', text)
    if m:
        val = float(m.group(1))
        if val < 1000:
            val *= 1000
        return val, val

    return None, None


# ── Experience extractor ──────────────────────────────────────────────────────

def extract_experience_requirement(text: str) -> Optional[float]:
    """
    Infers how many years of experience a job requires by collecting ALL
    signals from the text and returning the HIGHEST value found.

    Signal types:
      1. Explicit numeric ranges  — "3 to 5 years", "3-5 yrs"
      2. Explicit single values   — "3+ years of experience", "minimum 4 years"
      3. Level keywords           — junior → 2, senior → 5, lead → 6 …
      4. Soft phrases             — "several years" → 4, "extensive experience" → 5

    Returns None when no signals are detected.
    """
    candidates: list[float] = []

    for m in re.finditer(r'\b(\d+)\s*(?:to|[-–])\s*(\d+)\s*(?:years?|yrs?)', text, re.I):
        candidates.append((float(m.group(1)) + float(m.group(2))) / 2)

    for m in re.finditer(
        r'\b(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)', text, re.I
    ):
        candidates.append(float(m.group(1)))

    for m in re.finditer(
        r'(?:minimum|at\s+least|min\.?)\s*(\d+)\s*(?:years?|yrs?)', text, re.I
    ):
        candidates.append(float(m.group(1)))

    for keywords, years in LEVEL_KEYWORD_YEARS:
        if any(kw in text for kw in keywords):
            candidates.append(years)

    for phrases, years in SOFT_EXPERIENCE_PHRASES:
        if any(p in text for p in phrases):
            candidates.append(years)

    return max(candidates) if candidates else None


# ── Score functions ───────────────────────────────────────────────────────────

def score_profile(job: Job, profile: UserProfile) -> float:
    """
    Percentage-based skill match:
      score = (profile skills ∩ job skills) / |job skills| × 10

    Returns 5.0 (neutral) when no recognisable skills are found in the job.
    """
    text = (job.title + " " + job.description_snippet).lower()
    job_skills = {skill for skill in ALL_KNOWN_SKILLS if skill in text}

    if not job_skills:
        return 5.0

    matched = job_skills & set(profile.skills)
    return round(len(matched) / len(job_skills) * 10, 1)


def score_experience(job: Job, profile: UserProfile) -> float:
    """
    Compares the user's years of experience against the detected job requirement.

      user > required + 0.5   →  10.0  (clearly exceeds)
      |user − required| ≤ 0.5 →   9.0  (exact match window)
      user < required − 0.5   →  (user / required) × 9, min 1.0
      No requirement detected  →   5.0  (neutral)

    Also writes the detected requirement to job.experience_required.
    """
    text = (job.title + " " + job.description_snippet).lower()
    required = extract_experience_requirement(text)
    job.experience_required = required

    if required is None:
        return 5.0

    user = profile.experience_years
    gap  = required - user   # positive → user is below requirement

    if gap <= -0.5:
        return 10.0
    elif abs(gap) <= 0.5:
        return 9.0
    else:
        return round(max(1.0, (user / required) * 9), 1)


def score_salary(job: Job, profile: UserProfile) -> float:
    """
    Percentage-based salary score against the user's USD target.

      No salary listed                          →  5.0 (neutral)
      avg ≥ target, no geo restrictions         →  10.0
      avg ≥ target, but geo restrictions exist  →  6.0
      avg < target                              →  (avg / target) × 10 − 0.5 if restricted

    All salary figures are treated as USD regardless of the currency symbol in the job post.
    """
    if job.salary_min_usd is None:
        return 5.0

    text = (
        job.location + " " + job.salary_raw + " " +
        job.remote_info + " " + job.description_snippet
    ).lower()

    target = profile.salary_target_usd
    avg    = (job.salary_min_usd + (job.salary_max_usd or job.salary_min_usd)) / 2

    has_restrictions = any(w in text for w in [
        "us only", "united states only", "eu only", "europe only",
        "must be based", "must reside", "authorized to work in the us",
        "work authorization", "eligible to work in", "us citizens", "u.s. citizens",
        "right to work", "visa sponsorship not", "no sponsorship",
    ])

    if avg >= target:
        return 6.0 if has_restrictions else 10.0

    score = (avg / target) * 10
    if has_restrictions:
        score -= 0.5
    return round(max(1.0, score), 1)


def score_remote(job: Job) -> float:
    """
    Evaluates how remote-friendly the role is.
    Only called when profile.remote_only = true.

      10  work from anywhere / worldwide / fully distributed
       8  remote with relocation offered
       6  remote (country-restricted or unspecified)
       5  hybrid with travel benefit / open-to-remote
       3  hybrid, no travel benefit
       0  fully on-site
    """
    combined = (job.remote_info + " " + job.description_snippet).lower()

    if any(w in combined for w in [
        "work from anywhere", "worldwide", "global remote",
        "anywhere in the world", "fully distributed",
    ]):
        return 10.0

    is_remote = "remote" in combined

    if is_remote and any(w in combined for w in [
        "relocation", "relocation assistance", "relocation package",
        "we cover relocation", "relocation support",
    ]):
        return 8.0

    if is_remote and any(w in combined for w in [
        "us only", "united states only", "eu only", "europe only",
        "must be based", "must reside", "authorized to work in the us",
        "work authorization", "eligible to work in",
    ]):
        return 6.0

    if is_remote:
        return 6.0

    if any(w in combined for w in [
        "hybrid", "open to remote", "flexible remote",
        "travel reimburs", "travel stipend", "transport covered",
        "we cover travel", "travel allowance",
    ]):
        return 5.0

    if "hybrid" in combined:
        return 3.0

    return 0.0


def score_company(job: Job) -> float:
    """
    10  well-known company (in KNOWN_COMPANIES)
     5  unknown / not listed (default)
    """
    name = job.company.lower()
    return 10.0 if any(k in name for k in KNOWN_COMPANIES) else 5.0
