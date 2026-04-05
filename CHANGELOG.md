# Changelog

All notable changes to this project will be documented here.

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
