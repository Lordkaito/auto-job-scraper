"""
models.py
---------
Data model for a scraped job listing.
"""

from dataclasses import dataclass
from typing import Optional

from auto_job_scraper.config import WEIGHTS


@dataclass
class Job:
    title: str
    company: str
    url: str
    location: str = ""
    salary_raw: str = "Not specified"
    salary_min_usd: Optional[float] = None
    salary_max_usd: Optional[float] = None
    remote_info: str = ""
    description_snippet: str = ""
    keyword: str = ""

    # Component scores (each 1–10)
    score_profile: float = 5.0
    score_salary: float = 5.0
    score_experience: float = 5.0
    score_remote: float = 5.0
    score_company: float = 5.0
    score_final: float = 0.0

    # Detected experience requirement from the job post (years)
    experience_required: Optional[float] = None

    def compute_final_score(self, remote_only: bool = True) -> float:
        if remote_only:
            self.score_final = round(
                self.score_profile    * WEIGHTS["profile"]    +
                self.score_salary     * WEIGHTS["salary"]     +
                self.score_experience * WEIGHTS["experience"] +
                self.score_remote     * WEIGHTS["remote"]     +
                self.score_company    * WEIGHTS["company"],
                2,
            )
        else:
            # Remote scoring is disabled — redistribute its 15% equally across the other four
            bonus = WEIGHTS["remote"] / 4
            self.score_final = round(
                self.score_profile    * (WEIGHTS["profile"]    + bonus) +
                self.score_salary     * (WEIGHTS["salary"]     + bonus) +
                self.score_experience * (WEIGHTS["experience"] + bonus) +
                self.score_company    * (WEIGHTS["company"]    + bonus),
                2,
            )
        return self.score_final
