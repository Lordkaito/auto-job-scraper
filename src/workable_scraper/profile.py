"""
profile.py
----------
UserProfile dataclass — the user's personal data that drives all scoring.
Handles loading from / saving to ~/.workable-scraper/profile.toml.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROFILE_DIR  = Path.home() / ".workable-scraper"
PROFILE_FILE = PROFILE_DIR / "profile.toml"

# ── Default skill set (used for the --init template) ─────────────────────────

_DEFAULT_SKILLS: list[str] = sorted([
    "typescript", "javascript", "react", "next.js", "nextjs", "node.js", "nodejs",
    "graphql", "postgresql", "mysql", "sql", "php", "ruby", "rails",
    "redux", "zustand", "lit", "html", "css", "tailwind",
    "jest", "playwright", "testing", "eslint", "git", "github",
    "rest", "api", "agile", "ci/cd", "docker",
])

_DEFAULT_KEYWORDS: list[str] = [
    "fullstack software developer",
    "frontend developer",
    "backend developer",
    "software developer",
]


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    name:                  str       = "Your Name"
    experience_years:      float     = 0.0
    skills:                list[str] = field(default_factory=list)
    salary_target_usd:     int       = 50_000
    remote_only:           bool      = True
    search_keywords:       list[str] = field(default_factory=list)
    strict_experience:     bool      = True
    experience_gap:        float     = 0.5
    max_jobs_per_keyword:  int       = 20
    max_scan_per_keyword:  int       = 100
    min_score:             float     = 5.0


# ── Load / save ───────────────────────────────────────────────────────────────

def load_profile() -> Optional[UserProfile]:
    """Returns a UserProfile loaded from the config file, or None if not found."""
    if not PROFILE_FILE.exists():
        return None

    with open(PROFILE_FILE, "rb") as f:
        data = tomllib.load(f)

    p   = data.get("profile", {})
    sk  = data.get("skills",  {})
    sal = data.get("salary",  {})
    se  = data.get("search",  {})
    fi  = data.get("filters", {})

    return UserProfile(
        name                  = str(p.get("name", "Your Name")),
        experience_years      = float(p.get("experience_years", 0.0)),
        skills                = list(sk.get("list", [])),
        salary_target_usd     = int(sal.get("target_usd", 50_000)),
        remote_only           = bool(fi.get("remote_only", True)),
        search_keywords       = list(se.get("keywords", [])),
        strict_experience     = bool(fi.get("strict_experience", True)),
        experience_gap        = float(fi.get("experience_gap", 0.5)),
        max_jobs_per_keyword  = int(se.get("max_jobs_per_keyword", 20)),
        max_scan_per_keyword  = int(se.get("max_scan_per_keyword", 100)),
        min_score             = float(se.get("min_score", 5.0)),
    )


def save_profile(profile: UserProfile) -> None:
    """Serialises the profile to TOML and writes it to PROFILE_FILE."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(_render_toml(profile), encoding="utf-8")


def merge_cv_into_profile(existing: Optional[UserProfile], cv_data: dict) -> UserProfile:
    """
    Merges CV-extracted data into an existing profile (or creates a new one).
    CV data takes precedence for name, experience_years, and skills.
    Search/filter settings are preserved from the existing profile when available.
    """
    base = existing or UserProfile()

    if cv_data.get("name"):
        base.name = cv_data["name"]
    if cv_data.get("experience_years") is not None:
        base.experience_years = cv_data["experience_years"]
    if cv_data.get("skills"):
        base.skills = cv_data["skills"]

    return base


def default_profile() -> UserProfile:
    """Returns the built-in sample profile (used by --init)."""
    return UserProfile(
        name                  = "",
        experience_years      = 3.8,
        skills                = _DEFAULT_SKILLS,
        salary_target_usd     = 50_000,
        remote_only           = True,
        search_keywords       = _DEFAULT_KEYWORDS,
        strict_experience     = True,
        experience_gap        = 0.5,
        max_jobs_per_keyword  = 20,
        max_scan_per_keyword  = 100,
        min_score             = 5.0,
    )


# ── TOML renderer ─────────────────────────────────────────────────────────────

def _render_toml(p: UserProfile) -> str:
    skills_block   = "\n".join(f'    "{s}",' for s in p.skills)
    keywords_block = "\n".join(f'    "{k}",' for k in p.search_keywords)
    strict_str     = "true" if p.strict_experience else "false"

    remote_only_str = "true" if p.remote_only else "false"

    return f"""\
# Workable Job Scraper — User Profile
# ─────────────────────────────────────────────────────────────────
# Edit this file with your own information, then run:
#   workable-scraper
#
# To regenerate this file from a CV:
#   workable-scraper --cv path/to/your-cv.pdf
# ─────────────────────────────────────────────────────────────────

[profile]
name             = "{p.name}"
experience_years = {p.experience_years}   # total years of professional experience


[skills]
# These are matched against job descriptions to compute your profile score.
# Score = (your skills ∩ job's skills) / job's skills × 10
# Add or remove entries to match your actual tech stack.
list = [
{skills_block}
]


[salary]
# Your minimum acceptable salary per year.
# All salary figures (regardless of currency symbol in the job post) are treated as USD.
# Set a value that makes sense for your market.
target_usd = {p.salary_target_usd}


[search]
# Job titles to search for on Workable
keywords = [
{keywords_block}
]
max_jobs_per_keyword = {p.max_jobs_per_keyword}    # stop accepting once this many jobs pass per keyword
max_scan_per_keyword = {p.max_scan_per_keyword}   # stop visiting pages once this many are reviewed
min_score            = {p.min_score}              # jobs below this final score (0–10) are discarded


[filters]
# Set to true if you only want remote jobs.
# When true, jobs are scored on how remote-friendly they are (score_remote dimension, 15% weight).
# When false, remote scoring is skipped and its 15% weight is distributed equally
# across the other four dimensions (profile, salary, experience, company).
remote_only = {remote_only_str}

# If strict_experience is true, jobs requiring more years than yours
# (plus the gap below) are hard-filtered out regardless of their score.
# The gap only applies upward — jobs requiring fewer years always pass.
strict_experience = {strict_str}
experience_gap    = {p.experience_gap}   # e.g. 0.5 lets a 3.8-yr profile see jobs posted for 4.3 yrs
"""
