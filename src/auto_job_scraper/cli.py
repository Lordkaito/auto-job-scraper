"""
cli.py
------
Entry point. Handles argument parsing, profile loading, and the startup flow:

  auto-job-scraper --init       → write template profile.toml, exit
  auto-job-scraper --cv FILE    → parse CV, create/update profile.toml, run
  auto-job-scraper              → load existing profile.toml, run
                                   (if no profile: offer wizard or stop)
"""

import argparse
import asyncio
import sys
from datetime import datetime

from playwright.async_api import async_playwright

from auto_job_scraper import display
from auto_job_scraper.boards import available_boards, get_board
from auto_job_scraper.cv_parser import parse_cv
from auto_job_scraper.exporter import export_to_excel
from auto_job_scraper.models import Job
from auto_job_scraper.profile import (
    PROFILE_FILE,
    UserProfile,
    default_profile,
    load_profile,
    merge_cv_into_profile,
    save_profile,
)
from auto_job_scraper.scraper import search_keyword
from auto_job_scraper.wizard import run_wizard


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-job-scraper",
        description="Scrape Workable for remote jobs and score them against your profile.",
    )
    parser.add_argument(
        "--cv",
        metavar="PATH",
        help="Path to your CV/resume (PDF or .txt). Extracts your profile automatically.",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create a template profile.toml with sample data and exit.",
    )
    parser.add_argument(
        "--profile-path",
        action="store_true",
        help="Show the location of the profile config file and exit.",
    )
    parser.add_argument(
        "--remove-profile",
        action="store_true",
        help="Delete the profile config file and exit.",
    )
    parser.add_argument(
        "--board",
        choices=available_boards(),
        default=None,
        metavar="BOARD",
        help=(
            f"Job board to scrape. Available: {', '.join(available_boards())}. "
            "Overrides the job_board setting in profile.toml."
        ),
    )
    parser.add_argument(
        "--headless",
        choices=["true", "false"],
        default="true",
        metavar="true|false",
        help=(
            "Run the browser in headless mode (default: true). "
            "Use --headless false to open a visible browser window."
        ),
    )
    return parser


# ── Profile resolution ────────────────────────────────────────────────────────

def _resolve_profile(args: argparse.Namespace) -> UserProfile:
    """
    Determines the UserProfile to use based on args and existing config.
    May interact with the user (wizard) or exit early (--init).
    """

    # ── --profile-path: show config location and exit ────────────────────────
    if args.profile_path:
        exists = PROFILE_FILE.exists()
        status = "✔  exists" if exists else "✘  not found"
        print(f"\n  Profile config location  [{status}]")
        print(f"  File   : {display.file_link(str(PROFILE_FILE), PROFILE_FILE)}")
        print(f"  Folder : {display.file_link(str(PROFILE_FILE.parent), PROFILE_FILE.parent)}\n")
        sys.exit(0)

    # ── --remove-profile: delete config and exit ──────────────────────────────
    if args.remove_profile:
        if not PROFILE_FILE.exists():
            print(f"\n  ⚠  No profile found at {PROFILE_FILE}\n")
            sys.exit(0)
        print(f"\n  Profile found at: {PROFILE_FILE}")
        confirm = input("  Delete it? This cannot be undone. (y/n) [n]: ").strip().lower()
        if confirm == "y":
            PROFILE_FILE.unlink()
            print("  ✅ Profile deleted.\n")
        else:
            print("  Cancelled.\n")
        sys.exit(0)

    # ── --init: write template and exit ──────────────────────────────────────
    if args.init:
        profile = default_profile()
        save_profile(profile)
        print(f"\n  ✅ Template profile created!")
        print(f"  File   : {display.file_link(str(PROFILE_FILE), PROFILE_FILE)}")
        print(f"  Folder : {display.file_link(str(PROFILE_FILE.parent), PROFILE_FILE.parent)}")
        print()
        print("  Edit the file with your own information, then run:")
        print("    auto-job-scraper\n")
        sys.exit(0)

    # ── --cv: parse CV, create/update profile, then exit ─────────────────────
    if args.cv:
        print(f"\n  📄 Parsing CV: {args.cv}")
        try:
            cv_data = parse_cv(args.cv)
        except (FileNotFoundError, ValueError, ImportError) as e:
            print(f"  ❌ Could not parse CV: {e}")
            sys.exit(1)

        _report_cv_extraction(cv_data)

        existing = load_profile()
        profile  = merge_cv_into_profile(existing, cv_data)
        missing  = _find_missing_fields(profile)

        if missing:
            profile = _handle_missing_fields(profile, cv_data, missing)

        save_profile(profile)
        _print_profile_saved()
        sys.exit(0)

    # ── No args: look for existing profile ───────────────────────────────────
    profile = load_profile()
    if profile:
        print(f"\n  ✔  Loaded profile: {profile.name}  ({profile.experience_years} yrs exp)")
        return profile

    # ── No profile found: offer options ──────────────────────────────────────
    print("\n  ⚠  No profile found.")
    print(f"     Expected location: {PROFILE_FILE}\n")
    print("  You have three options:")
    print("    1.  auto-job-scraper --cv path/to/your-cv.pdf")
    print("    2.  auto-job-scraper --init  (creates an editable template) (recommended)")
    print("    3.  Answer a few questions now to build a profile\n")

    choice = input("  Continue with option 3 (interactive setup)? (y/n) [n]: ").strip().lower()
    if choice != "y":
        print("\n  Exiting. Run with --cv or --init to set up your profile.")
        sys.exit(0)

    profile = run_wizard()
    save_profile(profile)
    print(f"\n  💾 Profile saved to: {PROFILE_FILE}\n")
    return profile


def _report_cv_extraction(cv_data: dict) -> None:
    """Prints a summary of what was and wasn't detected from the CV."""
    print("\n  ─────────────────────────────────────────────────────────────")
    print("  CV extraction results")
    print("  ─────────────────────────────────────────────────────────────")

    name = cv_data.get("name")
    exp  = cv_data.get("experience_years")
    skills = cv_data.get("skills", [])

    print(f"  Name             : {name if name else '⚠  not detected'}")
    print(f"  Experience years : {exp if exp is not None else '⚠  not detected'}")

    if skills:
        skill_preview = ", ".join(skills[:10])
        suffix = f" … (+{len(skills) - 10} more)" if len(skills) > 10 else ""
        print(f"  Skills ({len(skills):2d} found) : {skill_preview}{suffix}")
    else:
        print("  Skills           : ⚠  none detected")

    print("  ─────────────────────────────────────────────────────────────")


def _find_missing_fields(profile: UserProfile) -> list[str]:
    """Returns a list of field names that are unset or at their empty default."""
    missing = []
    if not profile.name or profile.name == "Your Name":
        missing.append("name")
    if profile.experience_years == 0.0:
        missing.append("experience_years")
    if not profile.skills:
        missing.append("skills")
    if not profile.search_keywords:
        missing.append("search_keywords")
    return missing


def _handle_missing_fields(
    profile: UserProfile,
    cv_data: dict,
    missing: list[str],
) -> UserProfile:
    """
    Tells the user which fields are missing and offers two options:
      1. Answer questions now (wizard fills only the missing fields).
      2. Edit the config file manually (saves as-is and exits after).
    """
    print(f"\n  ⚠  The following fields could not be filled automatically:")
    for field in missing:
        print(f"       • {field.replace('_', ' ')}")

    print()
    print("  How would you like to fill them in?")
    print("    1. Answer a few questions now")
    print("    2. Edit the config file myself after it's saved")
    print()

    while True:
        choice = input("  Your choice (1 or 2) [2]: ").strip()
        if choice in ("", "1", "2"):
            break
        print("  Please enter 1 or 2.")

    if choice == "1":
        return run_wizard(prefilled={**cv_data, **_profile_to_prefill(profile)})

    # Option 2: save what we have, tell them to edit the file
    print()
    print("  The profile will be saved with the information found so far.")
    print("  Open the file and fill in the missing fields before running the scraper.")
    return profile


def _profile_to_prefill(profile: UserProfile) -> dict:
    """Converts a UserProfile to a prefill dict for the wizard."""
    return {
        "name":             profile.name if profile.name != "Your Name" else None,
        "experience_years": profile.experience_years if profile.experience_years != 0.0 else None,
        "skills":           profile.skills or [],
    }


def _print_profile_saved() -> None:
    print(f"\n  ✅ Profile saved!")
    print(f"  File   : {display.file_link(str(PROFILE_FILE), PROFILE_FILE)}")
    print(f"  Folder : {display.file_link(str(PROFILE_FILE.parent), PROFILE_FILE.parent)}")
    print()
    print("  When you're ready to start scraping, run:")
    print("    auto-job-scraper\n")


# ── Scraper runner ────────────────────────────────────────────────────────────

async def _run(profile: UserProfile, board_name: str, headless: bool = True) -> None:
    started_at = datetime.now()
    kw_total   = len(profile.search_keywords)
    board      = get_board(board_name)

    strict_label = (
        f"ON  (max {profile.experience_years + profile.experience_gap:.1f} yrs, "
        f"gap={profile.experience_gap})"
        if profile.strict_experience else "OFF"
    )

    print()
    print("╔" + "═" * 63 + "╗")
    print("║               🚀  Auto Job Scraper                    ║")
    print("╠" + "═" * 63 + "╣")
    print(f"║  User         : {profile.name:<46}║")
    print(f"║  Board        : {board.name:<46}║")
    print(f"║  Started      : {started_at.strftime('%Y-%m-%d %H:%M:%S'):<46}║")
    print(f"║  Keywords     : {kw_total} search terms{'':<36}║")
    print(
        f"║  Scan / Accept: {profile.max_scan_per_keyword} reviewed / "
        f"{profile.max_jobs_per_keyword} accepted per keyword{'':<13}║"
    )
    print(
        f"║  Min score    : {profile.min_score}   "
        f"Salary target: ${profile.salary_target_usd:,}/yr{'':<13}║"
    )
    print(f"║  Exp. filter  : {strict_label:<46}║")
    print("╚" + "═" * 63 + "╝")
    for i, kw in enumerate(profile.search_keywords, 1):
        print(f"    {i}. {kw}")
    print()

    all_jobs: list[Job] = []

    async with async_playwright() as p:
        mode_label = "headless" if headless else "windowed"
        print(f"  🌐 Launching {mode_label} Chromium browser...")
        try:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as e:
            if "executable" in str(e).lower() or "not found" in str(e).lower():
                print("\n  ❌ Chromium browser not found.")
                print("     Run this once to install it:")
                print("       playwright install chromium")
                print()
                sys.exit(1)
            raise
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        print("  ✔  Browser ready\n")

        await board.setup(page)

        for idx, keyword in enumerate(profile.search_keywords, 1):
            try:
                jobs = await search_keyword(page, keyword, idx, kw_total, profile, board)
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"\n  ⚠  Error on keyword '{keyword}': {e}")
            await asyncio.sleep(2)

        await board.teardown(page)
        await browser.close()
        print("\n  🛑 Browser closed")

    elapsed       = (datetime.now() - started_at).seconds
    minutes, secs = divmod(elapsed, 60)

    print()
    print("╔" + "═" * 63 + "╗")
    print("║                   📊  FINAL SUMMARY                       ║")
    print("╠" + "═" * 63 + "╣")
    print(f"║  Total jobs accepted : {len(all_jobs):<40}║")
    print(f"║  Time elapsed        : {minutes}m {secs}s{'':<37}║")
    print("╚" + "═" * 63 + "╝")

    if all_jobs:
        output_file = f"{board.name}_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        print(f"\n  💾 Exporting to {output_file}...")
        export_to_excel(all_jobs, output_file, profile)

        print(f"\n  🏆 Top 5 matches:")
        print(f"  {'─'*63}")
        top5 = sorted(all_jobs, key=lambda j: j.score_final, reverse=True)[:5]
        for i, job in enumerate(top5, 1):
            salary    = job.salary_raw[:30] if job.salary_raw != "Not specified" else "no salary listed"
            title     = display.link(job.title[:40], job.url)
            score_bar = display.bar(job.score_final)
            print(f"  {i}. {job.score_final:.1f}  {score_bar}  {title}")
            print(f"       @ {job.company[:40]}  —  {salary}")
        print(f"  {'─'*63}")
        print("  💡 Click a job title to open it in your browser")
    else:
        print("  ⚠  No jobs passed the minimum score threshold.")


# ── Entry points ──────────────────────────────────────────────────────────────

def main_cli() -> None:
    """Synchronous entry point registered by pyproject.toml."""
    parser     = _build_parser()
    args       = parser.parse_args()
    profile    = _resolve_profile(args)
    # --board overrides profile.toml; profile.job_board is the persisted default.
    board_name = args.board or profile.job_board
    headless   = args.headless.lower() != "false"
    asyncio.run(_run(profile, board_name, headless=headless))


if __name__ == "__main__":
    main_cli()
