# workable-job-scraper

A CLI tool that scrapes [Workable](https://jobs.workable.com) for job listings and scores them against your personal profile — skills, experience, and salary expectations — so the best matches rise to the top.

Results are exported to a formatted Excel file with colour-coded scores and clickable job links.

---

## Features

- Searches multiple job title keywords in one run
- Scores each job across up to five dimensions: skill match, salary, experience, remote accessibility, and company recognition
- Optional remote-only mode — when disabled, the remote weight is redistributed to the other dimensions
- Hard-filters jobs that exceed your experience level (optional)
- Exports results to Excel with per-job scores and a summary sheet
- Clickable job links in the terminal (top 5 matches after each run)
- Profile stored in a simple TOML config file you can edit any time

---

## Requirements

- Python 3.11 or higher
- A Chromium browser for scraping (installed separately — see below)

---

## Installation

```bash
pip install workable-job-scraper
```

### Installing the browser (one-time step)

This tool uses [Playwright](https://playwright.dev/python/) to automate a headless browser. After installing the package, you need to download the Chromium browser binary once:

```bash
playwright install chromium
```

This downloads Chromium to a local cache folder (`~/.cache/ms-playwright` on macOS/Linux, `%USERPROFILE%\AppData\Local\ms-playwright` on Windows). It does **not** install anything system-wide and does **not** require admin rights.

You only need to do this once per machine. If you skip this step, the scraper will tell you with a clear error message when you first run it.

---

## Setup

Before scraping, the tool needs to know your profile (skills, experience, salary, etc.). There are three ways to set it up:

### Option 1 — Import from your CV (recommended)

```bash
workable-scraper --cv path/to/your-cv.pdf
```

The tool will extract your name, years of experience, and tech skills from the file, show you what it found, and save a profile config. If anything couldn't be detected, it will ask you a few questions or let you edit the file yourself.

Supported formats: `.pdf`, `.txt`, `.md`

### Option 2 — Generate a template and fill it in

```bash
workable-scraper --init
```

Creates a pre-filled `profile.toml` with sample data and opens the folder so you can edit it directly. Fill in your details, then run the scraper.

### Option 3 — Answer questions interactively

```bash
workable-scraper
```

If no profile is found, the tool offers to walk you through a short setup wizard.

---

## Running the scraper

Once your profile is set up:

```bash
workable-scraper
```

The tool will:
1. Load your profile
2. Search Workable for each keyword in your config
3. Score every listing it finds
4. Export the results to an Excel file in your current directory
5. Print the top 5 matches in the terminal with clickable links

---

## Profile config

Your profile is stored at:

| Platform | Location |
|----------|----------|
| macOS / Linux | `~/.workable-scraper/profile.toml` |
| Windows | `C:\Users\<you>\.workable-scraper\profile.toml` |

You can open the file directly from the terminal:

```bash
workable-scraper --profile-path
```

The config file looks like this:

```toml
[profile]
name             = "Jane Doe"
experience_years = 4.0

[skills]
# Matched against job descriptions to compute your profile score.
list = [
    "typescript",
    "react",
    "node.js",
    "postgresql",
]

[salary]
# All salary figures are treated as USD regardless of the currency symbol in the job post.
target_usd = 55000

[search]
keywords = [
    "frontend developer",
    "fullstack developer",
]
max_jobs_per_keyword = 20
max_scan_per_keyword = 100
min_score            = 5.0

[filters]
# Set to true to score jobs on how remote-friendly they are.
# Set to false if you have no location preference — remote scoring is skipped
# and its weight is redistributed equally across the other four dimensions.
remote_only = true

# Hard-filter jobs that require more experience than you have (plus the gap).
strict_experience = true
experience_gap    = 0.5
```

---

## Scoring system

Each job is scored on up to five dimensions, then combined into a final weighted score (0-10):

| Dimension | Weight | How it works |
|-----------|--------|--------------|
| Profile match | 30% | % of the job's required skills that match yours |
| Salary | 25% | How close the listed salary is to your target (treated as USD) |
| Experience | 20% | How your years of experience compare to what the job requires |
| Remote | 15% | How remote-friendly the role is (only when `remote_only = true`) |
| Company | 10% | Bonus for well-known tech companies |

When `remote_only = false`, the Remote dimension is skipped and its 15% weight is distributed equally (+3.75% each) across the other four dimensions.

Jobs below `min_score` (default 5.0) are discarded. If `strict_experience` is enabled, jobs requiring more years than your profile (plus `experience_gap`) are hard-filtered before scoring.

---

## CLI reference

```
workable-scraper                    Run the scraper using your saved profile
workable-scraper --cv FILE          Parse a CV and create/update your profile, then exit
workable-scraper --init             Create a template profile.toml and exit
workable-scraper --profile-path     Show the location of your profile config file
workable-scraper --remove-profile   Delete your profile config file
```

---

## Updating your profile

To update your profile after getting a new CV:

```bash
workable-scraper --cv path/to/updated-cv.pdf
```

This merges the new CV data into your existing profile, preserving your search keywords and filter settings.

To edit the file directly at any time:

```bash
workable-scraper --profile-path   # shows the file location (clickable)
```

---

## License

MIT
