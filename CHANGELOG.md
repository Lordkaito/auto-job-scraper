# Changelog

All notable changes to this project will be documented here.

## [1.1.0] — 2026-04-06

### Multi-board architecture

- Introduced an abstract `JobBoard` base class (`boards/base.py`) that defines the standard interface all board implementations must satisfy (`setup`, `teardown`, `fetch_jobs`)
- Extracted all Workable-specific logic into `WorkableBoard` (`boards/workable.py`); the scraper orchestrator is now fully board-agnostic
- Added a board registry and factory (`boards/__init__.py`) — new boards are registered in one place with no changes required elsewhere
- Added `--board` CLI flag to override the job board for a single run without editing the config file
- Added `job_board` field to `profile.toml` (`[search]` section) so the preferred board is persisted per user

### Date-posted filter

- Added `date_posted_filter` to `profile.toml` (`[search]` section):
  - `0` — any time (default)
  - `1` — last 24 hours
  - `2` — last week
  - `3` — last month
- Filter is applied by interacting with Workable's native date combobox (`#day_range_input` → `#day_range_listbox`) rather than post-processing job dates
- Added `date_posted_filter` question to the interactive setup wizard

### Improved job data extraction

- Replaced fragile CSS-class selectors with stable `data-ui` attribute selectors throughout `_scrape_job_detail`:
  - `[data-ui='overview-company']`, `[data-ui='overview-location']`, `[data-ui='overview-workplace']`
  - `[data-ui='overview-date-posted']`
  - `[data-ui='job-breakdown-description-parsed-html']`, `[data-ui='job-breakdown-requirements-parsed-html']`, `[data-ui='job-breakdown-benefits-parsed-html']`
- Regex fallbacks retained for all fields in case optional sections are absent
- `description_snippet` now combines description, requirements, and benefits sections so every scoring function gets the full context it needs

### New job attributes

- `date_posted` — the posting date as shown on the job board
- `missing_skills` — skills detected in the job post that are absent from the user's profile (populated as a side-effect of `score_profile`)

### Excel export — new columns

- Added **Date Posted** (column 8) — when the job was posted
- Added **Missing Skills** (column 15) — skills in the job post not in your profile
- Final score, component scores, and link columns shifted right accordingly
- Output filename now prefixed with the board name: `<board>_jobs_<timestamp>.xlsx`

### `--headless` flag

- Added `--headless true|false` CLI flag (default: `true`)
- `--headless false` opens a visible Chromium window — useful for debugging or watching the scraper work
- Launch log reflects the selected mode: `"Launching headless Chromium browser..."` vs `"Launching windowed Chromium browser..."`

### Scoring

- `score_profile` now also writes `job.missing_skills` (sorted list of unmatched job skills) as a side-effect, consistent with how `score_experience` writes `job.experience_required`

---

## [1.0.0] — 2025-04-05

### Initial release

- Scrapes [Workable](https://jobs.workable.com) for remote job listings across multiple search keywords
- Scores each job on five dimensions: skill match, salary, experience, remote accessibility, and company recognition
- Percentage-based skill scoring — compares the job's required skills against your profile
- Experience scoring with level-keyword inference (junior / mid / senior / lead / principal) and explicit year detection
- Strict experience filter — optionally hard-filters jobs that exceed your experience level plus a configurable gap
- Salary scoring against configurable EUR and USD targets with geographic restriction detection
- Profile stored in `~/.workable-scraper/profile.toml` — human-readable TOML, fully editable
- CV import (`--cv`) — extracts name, experience years, and skills from PDF or plain-text CVs
- Interactive setup wizard for first-time users without a CV
- `--init` to generate a template profile config
- `--profile-path` to locate the config file (clickable link in the terminal)
- `--remove-profile` to delete the config file with confirmation
- Excel export with colour-coded scores, hyperlinks, per-keyword summary sheet, and run metadata
- Clickable top-5 job links in the terminal (OSC 8 hyperlinks)
- Headless Chromium via Playwright — no visible browser window
- Cross-platform: macOS, Windows, Linux
