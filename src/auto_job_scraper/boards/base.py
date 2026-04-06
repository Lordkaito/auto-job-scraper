"""
boards/base.py
--------------
Abstract base class that every job board implementation must satisfy.

Responsibilities split:
  Board (subclass)     — URL construction, authentication, cookie banners,
                         DOM navigation, scrolling/pagination, raw field extraction.
  Orchestrator         — salary parsing, all five scoring dimensions,
                         hard filters, result limits, export, display.
"""

from abc import ABC, abstractmethod

from playwright.async_api import Page

from auto_job_scraper.models import Job


class JobBoard(ABC):
    """
    Interface for a job board scraper.

    To add a new board:
      1. Subclass JobBoard in boards/<name>.py
      2. Set `name` and `base_url` class attributes
      3. Implement `fetch_jobs()`
      4. Optionally override `setup()` / `teardown()` for login or session cleanup
      5. Register the class in boards/__init__.py — nothing else needs to change
    """

    #: Short identifier used in filenames, CLI choices, and the board registry.
    #: Must be lowercase with no spaces (e.g. "workable", "linkedin").
    name: str = ""

    #: Root URL of the job board — used for display and the Info sheet.
    base_url: str = ""

    # ── Lifecycle hooks ───────────────────────────────────────────────────────

    async def setup(self, page: Page) -> None:
        """
        Called once before any keyword searches begin.

        Override to handle one-time concerns such as:
          - Navigating to a login page and submitting credentials
          - Accepting a global cookie/consent banner
          - Setting session cookies or localStorage tokens

        The default implementation is a no-op.
        """

    async def teardown(self, page: Page) -> None:
        """
        Called once after all keyword searches complete.

        Override for cleanup such as logging out or closing extra tabs.
        The default implementation is a no-op.
        """

    # ── Core contract ─────────────────────────────────────────────────────────

    @abstractmethod
    async def fetch_jobs(
        self,
        page: Page,
        keyword: str,
        max_scan: int,
        filters: dict | None = None,
    ) -> list[Job]:
        """
        Navigate the board, scroll or paginate, and extract raw job data
        for the given search keyword.

        Parameters
        ----------
        page:     Playwright Page — shared browser page, already initialised.
        keyword:  Search term exactly as provided by the user profile.
        max_scan: Maximum number of individual job listings to visit.
                  Stop opening new detail pages once this limit is reached.
        filters:  Optional dict of board-level search filters. Each board
                  reads only the keys it understands and ignores the rest.
                  Currently defined keys:
                    "date_posted_filter" int
                        0 = any time (default)
                        1 = last 24 hours
                        2 = last week
                        3 = last month

        Returns
        -------
        A list of Job objects with ONLY these fields populated:

            title               str   — job title
            company             str   — company name
            url                 str   — canonical URL of the job listing
            location            str   — free-text location (may be empty)
            salary_raw          str   — raw salary text as it appears on the page
            remote_info         str   — remote policy description
            description_snippet str   — excerpt of the job description
            keyword             str   — the search keyword that produced this job
            date_posted         str   — raw posting-date text (may be empty)

        All score fields (score_profile, score_salary, …, score_final) and
        salary_min_usd / salary_max_usd must be left at their dataclass
        defaults. The orchestrator in scraper.py fills them in after this
        method returns.
        """
        ...
