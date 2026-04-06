"""
boards/workable.py
------------------
Workable (jobs.workable.com) job board implementation.

All logic here was extracted verbatim from the original scraper.py;
no behavioural changes were made during the refactor.
"""

import asyncio
import re

from playwright.async_api import Page

from auto_job_scraper.boards.base import JobBoard
from auto_job_scraper.models import Job


# Maps the profile's date_posted_filter integer to the label text
# that Workable renders in its "Date posted" filter panel.
# Multiple variants are listed per value so the matcher stays robust
# against minor Workable UI copy changes.
_DATE_FILTER_LABELS: dict[int, list[str]] = {
    1: ["Last 24 hours", "Last day",   "24 hours"],
    2: ["Last week",     "Past week",  "7 days"],
    3: ["Last month",    "Past month", "30 days"],
}

_DATE_FILTER_NAMES: dict[int, str] = {
    0: "any time",
    1: "last 24 hours",
    2: "last week",
    3: "last month",
}


class WorkableBoard(JobBoard):
    name     = "workable"
    base_url = "https://jobs.workable.com"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def setup(self, page: Page) -> None:
        """Workable requires no login — cookie banners are dismissed per-page."""

    # ── Core contract ─────────────────────────────────────────────────────────

    async def fetch_jobs(
        self,
        page: Page,
        keyword: str,
        max_scan: int,
        filters: dict | None = None,
    ) -> list[Job]:
        """Navigate, scroll, and return raw Job objects for one keyword."""
        date_filter = (filters or {}).get("date_posted_filter", 0)

        url = f"{self.base_url}/search?query={keyword.replace(' ', '+')}"
        print("  → Loading search page...", flush=True)
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await self._dismiss_cookie_banner(page)

        if date_filter != 0:
            applied = await self._apply_date_filter(page, date_filter)
            if applied:
                print(f"    📅 Date filter: {_DATE_FILTER_NAMES[date_filter]}", flush=True)
                await asyncio.sleep(1.5)   # let results reload after filter click
            else:
                print(
                    f"    ⚠  Date filter '{_DATE_FILTER_NAMES.get(date_filter, date_filter)}' "
                    "could not be applied — showing all results",
                    flush=True,
                )

        await self._scroll_and_load(page, target_count=max_scan)

        all_links    = await self._get_job_links(page)
        remote_links = [j for j in all_links if j["isRemote"]]
        total_to_scan = min(len(remote_links), max_scan)

        print(f"  📋 Found: {len(all_links)} total listings | {len(remote_links)} remote")

        jobs: list[Job] = []
        scanned = 0

        for link_info in remote_links:
            if scanned >= max_scan:
                break

            job_url     = link_info["href"]
            title_short = link_info["title"][:48]
            progress    = f"[{scanned + 1:02d}/{total_to_scan:02d}]"

            print(f"  {progress} 🌐 {title_short:<48}")
            print("           └─ Loading job page...", end="\r", flush=True)

            detail = await self._scrape_job_detail(page, job_url)
            scanned += 1

            if not detail:
                print("           └─ ❌ Listing unavailable or removed                ")
                continue

            company_fallback = (
                job_url.split("-at-")[-1].replace("-", " ").title()
                if "-at-" in job_url else ""
            )

            jobs.append(Job(
                title               = link_info["title"],
                company             = detail.get("company") or company_fallback,
                url                 = job_url,
                location            = detail.get("location", ""),
                salary_raw          = detail.get("salary_raw", "Not specified"),
                remote_info         = detail.get("remote_info", ""),
                description_snippet = detail.get("description", ""),
                keyword             = keyword,
                date_posted         = detail.get("date_posted", ""),
            ))

            await asyncio.sleep(0.8)

        return jobs

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _dismiss_cookie_banner(self, page: Page) -> None:
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

    async def _scroll_and_load(self, page: Page, target_count: int = 100) -> None:
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

    async def _get_job_links(self, page: Page) -> list[dict]:
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

    async def _apply_date_filter(self, page: Page, filter_value: int) -> bool:
        """
        Opens Workable's "Date posted" combobox and selects the matching option.

        HTML structure (verified from Workable's search page):
          Container : [data-ui="day_range-select"]
          Combobox  : #day_range_input  — readonly text input; click opens the dropdown
          Listbox   : #day_range_listbox  — appears after click; holds [role="option"] items

        Returns True when an option was clicked, False on any failure.
        """
        if filter_value == 0:
            return True  # "Any time" — no interaction needed

        # Step 1: Click the combobox to open the dropdown.
        try:
            combobox = page.locator("#day_range_input").first
            if not await combobox.is_visible(timeout=3000):
                return False
            await combobox.click()
            await asyncio.sleep(0.5)
        except Exception:
            return False

        # Step 2: Wait for the listbox to become visible.
        try:
            listbox = page.locator("#day_range_listbox")
            await listbox.wait_for(state="visible", timeout=3000)
        except Exception:
            return False

        # Step 3: Click the [role="option"] whose text matches the desired period.
        # Multiple label variants are tried in order to tolerate minor copy changes.
        labels = _DATE_FILTER_LABELS.get(filter_value, [])
        for label in labels:
            try:
                option = listbox.locator(f"[role='option']:has-text('{label}')").first
                if await option.is_visible(timeout=1500):
                    await option.click()
                    return True
            except Exception:
                continue

        # Fallback: match by text anywhere inside the listbox (less precise but wider).
        for label in labels:
            try:
                option = listbox.get_by_text(label, exact=False).first
                if await option.is_visible(timeout=1000):
                    await option.click()
                    return True
            except Exception:
                continue

        return False

    async def _text(self, selector: str, page: Page) -> str:
        """
        Returns the trimmed inner text of the first element matching selector,
        or an empty string if the element is absent or raises.
        """
        try:
            el = page.locator(selector).first
            if await el.count() > 0:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    async def _scrape_job_detail(self, page: Page, url: str) -> dict:
        """
        Visits an individual job page and returns a dict of raw field values.
        Returns an empty dict when the listing is unavailable.

        Extraction strategy
        -------------------
        Primary:  stable data-ui attributes — these are semantic anchors that
                  Workable intentionally exposes and that survive CSS rebuilds.
        Fallback: regex on the full page text — used only when a data-ui
                  element is absent (e.g. optional sections like Benefits).
        """
        try:
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            await asyncio.sleep(1)
            await self._dismiss_cookie_banner(page)
            # Full page text is kept for two purposes only:
            #   1. Availability check ("listing not found")
            #   2. Last-resort fallback for salary and description
            text = await page.inner_text("main") or ""
        except Exception as e:
            print(f"    ⚠  Error loading {url}: {e}")
            return {}

        if "can't be found" in text or "not found" in text.lower():
            return {}

        # ── Company ───────────────────────────────────────────────────────────
        # data-ui="overview-company" renders as "at <Company Name>"
        company = await self._text("[data-ui='overview-company']", page)
        if company.lower().startswith("at "):
            company = company[3:].strip()
        if not company:
            m = re.search(r'at\s+([^\n]+)\s+(?:Remote|On-site|Hybrid)', text)
            company = m.group(1).strip() if m else ""

        # ── Location ──────────────────────────────────────────────────────────
        location = await self._text("[data-ui='overview-location']", page)
        if not location:
            m = re.search(
                r'(?:Remote|On-site|Hybrid)\s*([^\n]+?)\s*(?:Full-time|Part-time|Posted)', text
            )
            location = m.group(1).strip() if m else ""

        # ── Remote / workplace type ───────────────────────────────────────────
        # data-ui="overview-workplace" gives a clean canonical value:
        # "Remote", "Hybrid", or "On-site". The richer remote-policy language
        # needed by score_remote() is covered by description_snippet below.
        remote_info = await self._text("[data-ui='overview-workplace']", page)
        if not remote_info:
            if re.search(r'fully remote|100% remote|work from anywhere|worldwide remote', text, re.I):
                remote_info = "fully remote - worldwide"
            elif re.search(r'remote', text, re.I):
                snippet     = re.search(r'.{0,100}remote.{0,100}', text, re.I)
                remote_info = f"remote - {snippet.group().strip()[:120]}" if snippet else "remote"
            else:
                remote_info = "on-site"

        # ── Date posted ───────────────────────────────────────────────────────
        # Not used in scoring yet — stored for future date-based filtering.
        date_posted = await self._text("[data-ui='overview-date-posted']", page)

        # ── Content sections ──────────────────────────────────────────────────
        # Each section is extracted independently via its data-ui anchor.
        # They are combined into description_snippet so every scoring function
        # gets the text it needs without changing its interface:
        #   score_profile    → skills from description + requirements
        #   score_experience → year counts / level keywords from requirements
        #   score_salary     → salary figures / geo-restrictions from benefits
        #   score_remote     → remote-policy language from description + benefits
        description_text  = await self._text("[data-ui='job-breakdown-description-parsed-html']",  page)
        requirements_text = await self._text("[data-ui='job-breakdown-requirements-parsed-html']", page)
        benefits_text     = await self._text("[data-ui='job-breakdown-benefits-parsed-html']",     page)

        # Fallback: data-ui description not found — extract from full page text
        if not description_text:
            m = re.search(r'\bDescription\b\s*([\s\S]+)', text, re.I)
            description_text = m.group(1).strip() if m else text

        # ── Salary ────────────────────────────────────────────────────────────
        # Search the most specific source first (benefits), then description,
        # then the full page text as a last resort.
        _salary_patterns = [
            r'(?:salary|compensation|pay|range)[:\s]*([€$£\d,\.\-kK\s]+(?:USD|EUR|GBP|per year|annually|/yr)?)',
            r'([€$£]\s*[\d,]+(?:[Kk])?(?:\s*[-–]\s*[€$£]?\s*[\d,]+[Kk]?)?)',
            r'(\d{2,3}[Kk]\s*[-–]\s*\d{2,3}[Kk])',
        ]
        salary_raw = "Not specified"
        for search_text in [benefits_text, description_text, text]:
            if not search_text:
                continue
            for pat in _salary_patterns:
                m = re.search(pat, search_text, re.IGNORECASE)
                if m:
                    salary_raw = m.group(1).strip()
                    break
            if salary_raw != "Not specified":
                break

        # ── Assemble description_snippet ──────────────────────────────────────
        description_snippet = "\n\n".join(
            part for part in [description_text, requirements_text, benefits_text] if part
        )

        return {
            "company":     company,
            "location":    location,
            "remote_info": remote_info,
            "date_posted": date_posted,
            "salary_raw":  salary_raw,
            "description": description_snippet,
        }
