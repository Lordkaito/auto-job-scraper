"""
scraper.py
----------
Playwright-based browser automation: page loading, scrolling,
link extraction, job detail scraping, and per-keyword search loop.
"""

import asyncio
import re

from playwright.async_api import Page

from auto_job_scraper import display
from auto_job_scraper.config import BASE_URL
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


# ── Cookie banner ─────────────────────────────────────────────────────────────

async def dismiss_cookie_banner(page: Page) -> None:
    """Tries common selectors to decline/close a cookie consent banner."""
    selectors = [
        "button#onetrust-reject-all-handler",
        "button[id*='reject']",
        "button[class*='reject']",
        "button:has-text('Reject all')",
        "button:has-text('Reject All')",
        "button:has-text('Decline all')",
        "button:has-text('Decline All')",
        "button:has-text('Decline')",
        "button:has-text('Reject')",
        "button:has-text('No, thanks')",
        "button:has-text('No thanks')",
        "[aria-label*='reject' i]",
        "[aria-label*='decline' i]",
        "[data-testid*='reject' i]",
        "[data-testid*='decline' i]",
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=800):
                await btn.click()
                await asyncio.sleep(0.5)
                print("    🍪 Cookie banner dismissed")
                return
        except Exception:
            continue


# ── Infinite scroll ───────────────────────────────────────────────────────────

async def scroll_and_load(page: Page, target_count: int = 100) -> None:
    """Scrolls the results page until at least target_count jobs are loaded."""
    prev_count = 0
    print(f"   ↕  Scrolling to load up to {target_count} jobs...", flush=True)
    for attempt in range(1, 21):
        count  = await page.evaluate(
            "document.querySelectorAll('a[href*=\"/view/\"]').length"
        )
        unique = count // 2
        print(
            f"   ↕  Scroll pass {attempt:02d} — {unique} jobs loaded so far...",
            end="\r", flush=True,
        )
        if count >= target_count * 2:
            break
        if count == prev_count:
            break
        prev_count = count
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.5)
    print(f"   ↕  Done scrolling — {prev_count // 2} jobs detected.          ", flush=True)


# ── Link extraction ───────────────────────────────────────────────────────────

async def get_job_links(page: Page) -> list[dict]:
    """Returns a deduplicated list of job link dicts from the current page."""
    return await page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a[href*="/view/"]'));
            const seen  = new Set();
            const jobs  = [];
            links.forEach(a => {
                if (!seen.has(a.href) && a.innerText?.trim()) {
                    seen.add(a.href);
                    jobs.push({
                        title:    a.innerText.trim(),
                        href:     a.href,
                        isRemote: a.href.includes('remote'),
                    });
                }
            });
            return jobs;
        }
    """)


# ── Job detail page ───────────────────────────────────────────────────────────

async def scrape_job_detail(page: Page, url: str) -> dict:
    """
    Visits an individual job page and extracts:
    salary_raw, remote_info, description, company, location.
    Returns an empty dict when the listing is unavailable.
    """
    try:
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await dismiss_cookie_banner(page)
        text = await page.inner_text("main") or ""
    except Exception as e:
        print(f"    ⚠  Error loading {url}: {e}")
        return {}

    if "can't be found" in text or "not found" in text.lower():
        return {}

    # Salary
    salary_raw = "Not specified"
    for pat in [
        r'(?:salary|compensation|pay|range)[:\s]*([€$£\d,\.\-kK\s]+(?:USD|EUR|GBP|per year|annually|/yr)?)',
        r'([€$£]\s*[\d,]+(?:[Kk])?(?:\s*[-–]\s*[€$£]?\s*[\d,]+[Kk]?)?)',
        r'(\d{2,3}[Kk]\s*[-–]\s*\d{2,3}[Kk])',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            salary_raw = m.group(1).strip()
            break

    # Remote info
    remote_info = "on-site"
    if re.search(r'fully remote|100% remote|work from anywhere|worldwide remote', text, re.I):
        remote_info = "fully remote - worldwide"
    elif re.search(r'remote', text, re.I):
        snippet     = re.search(r'.{0,100}remote.{0,100}', text, re.I)
        remote_info = f"remote - {snippet.group().strip()[:120]}" if snippet else "remote"

    # Description snippet
    desc_match  = re.search(r'Description\s*(.{100,600})', text, re.I | re.DOTALL)
    description = desc_match.group(1).replace('\n', ' ').strip() if desc_match else text[:500]

    # Company and location
    company_match = re.search(r'at\s+([^\n]+)\s+(?:Remote|On-site|Hybrid)', text)
    company       = company_match.group(1).strip() if company_match else ""

    location_match = re.search(
        r'(?:Remote|On-site|Hybrid)\s*([^\n]+?)\s*(?:Full-time|Part-time|Posted)', text
    )
    location = location_match.group(1).strip() if location_match else ""

    return {
        "salary_raw":  salary_raw,
        "remote_info": remote_info,
        "description": description,
        "company":     company,
        "location":    location,
    }


# ── Keyword search loop ───────────────────────────────────────────────────────

async def search_keyword(
    page: Page,
    keyword: str,
    kw_index: int,
    kw_total: int,
    profile: UserProfile,
) -> list[Job]:
    """Runs a full search for one keyword, scores each job, returns accepted list."""
    print(f"\n{'='*65}")
    print(f"  [{kw_index}/{kw_total}] 🔍  Searching: \"{keyword}\"")
    print(f"{'='*65}")

    url = f"{BASE_URL}/search?query={keyword.replace(' ', '+')}"
    print("  → Loading search page...", flush=True)
    await page.goto(url, timeout=20000, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    await dismiss_cookie_banner(page)
    await scroll_and_load(page, target_count=profile.max_scan_per_keyword)

    all_links    = await get_job_links(page)
    remote_links = [j for j in all_links if j["isRemote"]]

    print(f"  📋 Found: {len(all_links)} total listings | {len(remote_links)} remote")
    print(
        f"  🎯 Will scan up to {profile.max_scan_per_keyword}, "
        f"accept up to {profile.max_jobs_per_keyword}\n"
    )

    jobs_accepted: list[Job] = []
    jobs_scanned  = 0
    total_to_scan = min(len(remote_links), profile.max_scan_per_keyword)

    for link_info in remote_links:
        if jobs_scanned >= profile.max_scan_per_keyword:
            print(f"\n  ⏹  Scan limit reached ({profile.max_scan_per_keyword} reviewed)")
            break
        if len(jobs_accepted) >= profile.max_jobs_per_keyword:
            print(f"\n  ✅  Acceptance limit reached ({profile.max_jobs_per_keyword} accepted)")
            break

        job_url        = link_info["href"]
        title_short    = link_info["title"][:48]
        progress       = f"[{jobs_scanned + 1:02d}/{total_to_scan:02d}]"
        accepted_tally = f"  ✔ {len(jobs_accepted)} accepted"

        print(f"  {progress} 🌐 {title_short:<48} {accepted_tally}")
        print("           └─ Loading job page...", end="\r", flush=True)

        detail = await scrape_job_detail(page, job_url)
        jobs_scanned += 1

        if not detail:
            print("           └─ ❌ Listing unavailable or removed                ")
            continue

        job = Job(
            title=link_info["title"],
            company=detail.get(
                "company",
                job_url.split("-at-")[-1].replace("-", " ").title() if "-at-" in job_url else "",
            ),
            url=job_url,
            location=detail.get("location", ""),
            salary_raw=detail.get("salary_raw", "Not specified"),
            remote_info=detail.get("remote_info", ""),
            description_snippet=detail.get("description", ""),
            keyword=keyword,
        )

        if not job.company and "-at-" in job_url:
            job.company = job_url.split("-at-")[-1].replace("-", " ").title()

        job.salary_min_usd, job.salary_max_usd = parse_salary(job.salary_raw)

        job.score_profile    = score_profile(job, profile)
        job.score_salary     = score_salary(job, profile)
        job.score_experience = score_experience(job, profile)
        job.score_remote     = score_remote(job) if profile.remote_only else 5.0
        job.score_company    = score_company(job)
        job.compute_final_score(remote_only=profile.remote_only)

        score_bar     = display.bar(job.score_final)
        label         = display.score_label(job.score_final)
        salary_str    = job.salary_raw[:35] if job.salary_raw != "Not specified" else "—"
        exp_str       = (
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

        if job.score_final > profile.min_score:
            jobs_accepted.append(job)
            print("              ✅ ACCEPTED")
        else:
            print(f"              ⛔ Rejected (score {job.score_final:.1f} ≤ {profile.min_score})")

        await asyncio.sleep(0.8)

    print(f"\n  {'─'*63}")
    print(f"  📊 '{keyword}' done: {len(jobs_accepted)} accepted / {jobs_scanned} scanned")
    print(f"  {'─'*63}")
    return jobs_accepted
