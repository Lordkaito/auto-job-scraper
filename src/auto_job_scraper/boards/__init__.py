"""
boards/__init__.py
------------------
Central registry of all available job board implementations.

Adding a new board
------------------
1. Create  boards/<name>.py  with a class that subclasses JobBoard.
2. Import that class below and add it to BOARDS.
   That's the only file that needs to change — CLI choices, wizard options,
   and the orchestrator all derive their information from this dict.

Example
-------
    from auto_job_scraper.boards.linkedin import LinkedInBoard

    BOARDS: dict[str, type[JobBoard]] = {
        "workable": WorkableBoard,
        "linkedin": LinkedInBoard,   # ← one new line
    }
"""

from auto_job_scraper.boards.base import JobBoard
from auto_job_scraper.boards.workable import WorkableBoard

BOARDS: dict[str, type[JobBoard]] = {
    "workable": WorkableBoard,
    # "linkedin":  LinkedInBoard,   # uncomment when implemented
    # "indeed":    IndeedBoard,
    # "wellfound": WellfoundBoard,
}


def get_board(name: str) -> JobBoard:
    """
    Instantiate and return the named board.
    Raises ValueError when the name is not registered.
    """
    if name not in BOARDS:
        available = ", ".join(sorted(BOARDS))
        raise ValueError(
            f"Unknown job board '{name}'. Available boards: {available}"
        )
    return BOARDS[name]()


def available_boards() -> list[str]:
    """Returns a sorted list of all registered board names."""
    return sorted(BOARDS.keys())
