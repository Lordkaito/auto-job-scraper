# auto-job-scraper

A CLI tool that scrapes job boards and scores listings against your personal profile — skills, experience, and salary expectations — so the best matches rise to the top.

Currently supports [Workable](https://jobs.workable.com). The architecture is designed so additional job boards can be added without touching existing code.

Results are exported to a formatted Excel file with colour-coded scores, clickable job links, and a breakdown of missing skills per listing.

---

## Features

- Searches multiple job title keywords in one run
- Scores each job across up to five dimensions: skill match, salary, experience, remote accessibility, and company recognition
- Optional remote-only mode — when disabled, the remote weight is redistributed to the other dimensions
- Hard-filters jobs that exceed your experience level (optional)
- Date-posted filter — limit results to the last 24 hours, last week, or last month
- Exports results to Excel with per-job scores, missing skills, date posted, and a summary sheet
- Clickable job links in the terminal (top 5 matches after each run)
- Profile stored in a simple TOML config file you can edit any time
- Multi-board architecture — new job boards can be added with minimal code changes
- `--headless false` flag to watch the browser work in a visible window

---

## Requirements

- Python 3.11 or higher
- A Chromium browser for scraping (installed separately — see below)

---

## Installation

```bash
pip install auto-job-scraper
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

### Option 1 — Import from your CV

```bash
auto-job-scraper --cv path/to/your-cv.pdf
```

The tool will extract your name, years of experience, and tech skills from the file, show you what it found, and save a profile config. If anything couldn't be detected, it will ask you a few questions or let you edit the file yourself.

Supported formats: `.pdf`, `.txt`, `.md`

### Option 2 — Generate a template and fill it in (recommended)

```bash
auto-job-scraper --init
```

Creates a pre-filled `profile.toml` with sample data and opens the folder so you can edit it directly. Fill in your details, then run the scraper.

### Option 3 — Answer questions interactively

```bash
auto-job-scraper
```

If no profile is found, the tool offers to walk you through a short setup wizard.

---

## Running the scraper

Once your profile is set up:

```bash
auto-job-scraper
```

The tool will:
1. Load your profile
2. Search for each keyword in your config
3. Score every listing it finds
4. Export the results to an Excel file in your current directory
5. Print the top 5 matches in the terminal with clickable links

To watch the browser as it works (useful for debugging or curiosity):

```bash
auto-job-scraper --headless false
```

To run against a specific job board for this session only:

```bash
auto-job-scraper --board workable
```

---

## Profile config

Your profile is stored at:

| Platform | Location |
|----------|----------|
| macOS / Linux | `~/.auto-job-scraper/profile.toml` |
| Windows | `C:\Users\<you>\.auto-job-scraper\profile.toml` |

You can open the file directly from the terminal:

```bash
auto-job-scraper --profile-path
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
# Which job board to scrape. Available boards: workable
job_board = "workable"

keywords = [
    "frontend developer",
    "fullstack developer",
]
max_jobs_per_keyword = 20
max_scan_per_keyword = 100
min_score            = 5.0

# How recent should job postings be?
#   0 = any time (default — no date restriction)
#   1 = last 24 hours
#   2 = last week
#   3 = last month
date_posted_filter = 0

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

Each job is scored on up to five dimensions, then combined into a final weighted score (0–10):

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

## Excel output

Each run produces an `.xlsx` file named `<board>_jobs_<timestamp>.xlsx` with three sheets:

### Jobs sheet

One row per accepted job, sorted by final score (highest first). Columns:

| # | Column | Description |
|---|--------|-------------|
| 1 | Keyword | The search term that found this job |
| 2 | Title | Job title |
| 3 | Company | Company name |
| 4 | Location | Office location or "Remote" |
| 5 | Salary | Normalised salary range in USD (raw text shown below) |
| 6 | Exp. Required | Years of experience detected in the job post |
| 7 | Remote | Remote policy extracted from the listing |
| 8 | Date Posted | When the job was posted (as shown on the board) |
| 9 | Final Score | Weighted score 0–10, colour-coded green / yellow / red |
| 10–14 | Component scores | Profile, Salary, Experience, Remote, Company (each 1–10) |
| 15 | Missing Skills | Skills found in the job post that are absent from your profile |
| 16 | Link | Clickable hyperlink to the original listing |

Score colour coding: **green** ≥ 8.0 · **yellow** ≥ 6.5 · **red** < 6.5

### Summary sheet

One row per keyword — total jobs accepted, average score, and best score.

### Info sheet

Run metadata: date, user, board, weights used, and filter settings.

---

## CLI reference

```
auto-job-scraper                       Run the scraper using your saved profile
auto-job-scraper --cv FILE             Parse a CV and create/update your profile, then exit
auto-job-scraper --init                Create a template profile.toml and exit
auto-job-scraper --profile-path        Show the location of your profile config file
auto-job-scraper --remove-profile      Delete your profile config file

auto-job-scraper --board BOARD         Override the job board for this run
                                         (overrides job_board in profile.toml)
                                         Available: workable

auto-job-scraper --headless false      Open a visible browser window instead of
                                         running headless (default: true)
```

---

## Updating your profile

To update your profile after getting a new CV:

```bash
auto-job-scraper --cv path/to/updated-cv.pdf
```

This merges the new CV data into your existing profile, preserving your search keywords and filter settings.

To edit the file directly at any time:

```bash
auto-job-scraper --profile-path   # shows the file location (clickable)
```

---

## License

MIT
