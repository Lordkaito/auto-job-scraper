"""
wizard.py
---------
Interactive Q&A flow for first-time setup when no CV or profile is provided.
Asks only the questions needed to build a complete UserProfile.
"""

from workable_scraper.config import ALL_KNOWN_SKILLS
from workable_scraper.profile import UserProfile


def run_wizard(prefilled: dict | None = None) -> UserProfile:
    """
    Walks the user through setup questions and returns a populated UserProfile.

    prefilled: optional dict from a partial CV parse (name, experience_years,
               skills) — pre-fills those answers so the user only fills gaps.
    """
    pre = prefilled or {}

    print("\n  ─────────────────────────────────────────────────────────────")
    print("  📝  Profile setup — press Enter to keep the shown default.")
    print("  ─────────────────────────────────────────────────────────────\n")

    # ── Name ──────────────────────────────────────────────────────────────────
    name = _ask_str(
        "  Your full name",
        default=pre.get("name") or "Your Name",
    )

    # ── Experience ────────────────────────────────────────────────────────────
    exp_default = pre.get("experience_years")
    if exp_default is not None:
        print(f"\n  Detected {exp_default} years of experience from your CV.")
    experience_years = _ask_float(
        "  Years of professional experience",
        default=exp_default if exp_default is not None else 0.0,
    )

    # ── Skills ────────────────────────────────────────────────────────────────
    pre_skills = pre.get("skills", [])
    if pre_skills:
        print(f"\n  Skills detected from your CV ({len(pre_skills)} found):")
        print(f"  {', '.join(pre_skills)}")
        keep = input("  Keep these skills? (y/n) [y]: ").strip().lower()
        skills = pre_skills if keep != "n" else []
    else:
        skills = []

    if not skills:
        print(f"\n  Known skills you can pick from:")
        print(f"  {', '.join(sorted(ALL_KNOWN_SKILLS))}\n")
        raw = input("  Enter your skills (comma-separated): ").strip()
        skills = [s.strip().lower() for s in raw.split(",") if s.strip()]

    # ── Salary ────────────────────────────────────────────────────────────────
    print()
    print("  All salary comparisons use USD. Non-USD amounts in job posts are converted automatically.")
    salary_usd = int(_ask_float("  Salary target $/year", default=50_000))

    # ── Remote preference ─────────────────────────────────────────────────────
    print()
    remote_raw = input(
        "  Are you looking for remote jobs only? (y/n) [y]: "
    ).strip().lower()
    remote_only = remote_raw != "n"

    # ── Search keywords ───────────────────────────────────────────────────────
    print("\n  Job title keywords to search for (comma-separated).")
    print("  e.g.  fullstack software developer, frontend developer")
    kw_raw   = input("  Keywords [software developer]: ").strip()
    keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
    if not keywords:
        keywords = ["software developer"]

    # ── Experience filter ─────────────────────────────────────────────────────
    print()
    strict_raw = input(
        "  Enable strict experience filter?\n"
        "  (jobs requiring more years than yours are skipped) (y/n) [y]: "
    ).strip().lower()
    strict = strict_raw != "n"

    gap = 0.5
    if strict:
        gap = _ask_float(
            "  Experience gap — tolerance above your years (e.g. 0.5)",
            default=0.5,
        )

    # ── Limits & thresholds ───────────────────────────────────────────────────
    print()
    max_jobs  = int(_ask_float("  Max jobs to accept per keyword",       default=20))
    max_scan  = int(_ask_float("  Max job listings to scan per keyword", default=100))
    min_score = _ask_float("  Minimum score to accept a job (0–10)",     default=5.0)

    return UserProfile(
        name                  = name,
        experience_years      = experience_years,
        skills                = skills,
        salary_target_usd     = salary_usd,
        remote_only           = remote_only,
        search_keywords       = keywords,
        strict_experience    = strict,
        experience_gap       = gap,
        max_jobs_per_keyword = max_jobs,
        max_scan_per_keyword = max_scan,
        min_score            = min_score,
    )


# ── Input helpers ─────────────────────────────────────────────────────────────

def _ask_str(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def _ask_float(prompt: str, default: float) -> float:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("    ⚠  Please enter a number.")
