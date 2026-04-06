"""
scraper.py
----------
Board-agnostic orchestrator: scores the raw jobs returned by a JobBoard,
applies hard filters, enforces per-keyword limits, and collects results.

Board-specific concerns (URL construction, DOM navigation, scrolling,
cookie banners, field extraction) live in boards/<name>.py.
"""

from playwright.async_api import Page

from auto_job_scraper import display
from auto_job_scraper.boards.base import JobBoard
from auto_job_scraper.models import Job
from auto_job_scraper.profile import UserProfile
from auto_job_scraper.scoring import (
    parse_salary,
    score_company,
    score_experience,
    score_profile,
    score_remote,
    score_salary,
)


async def search_keyword(
    page: Page,
    keyword: str,
    kw_index: int,
    kw_total: int,
    profile: UserProfile,
    board: JobBoard,
) -> list[Job]:
    """
    Runs a full search for one keyword using the given board.

    1. Delegates all scraping to board.fetch_jobs() — board owns extraction.
    2. Scores each returned job across all five dimensions.
    3. Applies hard experience filter and minimum-score threshold.
    4. Enforces max_jobs_per_keyword acceptance limit.
    """
    print(f"\n{'='*65}")
    print(f"  [{kw_index}/{kw_total}] 🔍  Searching: \"{keyword}\"  [{board.name}]")
    print(f"{'='*65}")
    print(
        f"  🎯 Will scan up to {profile.max_scan_per_keyword}, "
        f"accept up to {profile.max_jobs_per_keyword}\n"
    )

    # ── 1. Fetch raw jobs from the board ─────────────────────────────────────
    raw_jobs = await board.fetch_jobs(
        page,
        keyword,
        profile.max_scan_per_keyword,
        filters={"date_posted_filter": profile.date_posted_filter},
    )

    # ── 2. Score, filter, and collect ────────────────────────────────────────
    jobs_accepted: list[Job] = []

    for job in raw_jobs:
        if len(jobs_accepted) >= profile.max_jobs_per_keyword:
            print(f"\n  ✅  Acceptance limit reached ({profile.max_jobs_per_keyword} accepted)")
            break

        # Salary parsing (needed by score_salary)
        job.salary_min_usd, job.salary_max_usd = parse_salary(job.salary_raw)

        # Five scoring dimensions
        job.score_profile    = score_profile(job, profile)
        job.score_salary     = score_salary(job, profile)
        job.score_experience = score_experience(job, profile)   # also sets job.experience_required
        job.score_remote     = score_remote(job) if profile.remote_only else 5.0
        job.score_company    = score_company(job)
        job.compute_final_score(remote_only=profile.remote_only)

        score_bar  = display.bar(job.score_final)
        label      = display.score_label(job.score_final)
        salary_str = job.salary_raw[:35] if job.salary_raw != "Not specified" else "—"
        exp_str    = (
            f"{job.experience_required:.0f} yrs required"
            if job.experience_required is not None else "not listed"
        )

        print(f"           └─ Score: {job.score_final:.1f}/10  {score_bar}  [{label}]")
        print(
            f"              profile={job.score_profile} | salary={job.score_salary} | "
            f"exp={job.score_experience} | remote={job.score_remote} | company={job.score_company}"
        )
        print(f"              Salary: {salary_str}  |  Experience: {exp_str}")

        # Hard experience filter
        if profile.strict_experience and job.experience_required is not None:
            max_allowed = profile.experience_years + profile.experience_gap
            if job.experience_required > max_allowed:
                print(
                    f"              🚫 Strict filter: requires {job.experience_required:.1f} yrs "
                    f"> allowed {max_allowed:.1f} yrs — skipped"
                )
                continue

        # Minimum-score filter
        if job.score_final > profile.min_score:
            jobs_accepted.append(job)
            print("              ✅ ACCEPTED")
        else:
            print(f"              ⛔ Rejected (score {job.score_final:.1f} ≤ {profile.min_score})")

    print(f"\n  {'─'*63}")
    print(f"  📊 '{keyword}' done: {len(jobs_accepted)} accepted / {len(raw_jobs)} scanned")
    print(f"  {'─'*63}")
    return jobs_accepted
