"""
config.py
---------
Algorithmic constants — not user-specific.
Everything a user would customise lives in ~/.auto-job-scraper/profile.toml.

Note: BASE_URL has been removed from this file.
Each board now owns its own base_url as a class attribute in boards/<name>.py.
"""

# ── Scoring weights (must sum to 1.0) ─────────────────────────────────────────

WEIGHTS: dict[str, float] = {
    "profile":    0.30,
    "salary":     0.25,
    "experience": 0.20,
    "remote":     0.15,
    "company":    0.10,
}

# ── Broad skill dictionary ────────────────────────────────────────────────────
# Used to detect what technologies a job post requires.
# Profile score = (user skills ∩ job skills) / |job skills| × 10

ALL_KNOWN_SKILLS: set[str] = {
    # Languages
    "typescript", "javascript", "python", "ruby", "php", "java", "go", "rust",
    "c#", "c++", "swift", "kotlin", "scala", "elixir", "clojure", "r",
    # Frontend
    "react", "next.js", "nextjs", "vue", "angular", "svelte", "lit",
    "html", "css", "tailwind", "sass", "scss", "webpack", "vite", "astro",
    # Backend
    "node.js", "nodejs", "rails", "django", "laravel", "express", "fastapi",
    "spring", "nestjs", "flask", "sinatra", "phoenix",
    # Databases
    "postgresql", "mysql", "sql", "mongodb", "redis", "elasticsearch",
    "sqlite", "dynamodb", "cassandra", "neo4j", "supabase", "firebase",
    # State management
    "redux", "zustand", "mobx", "recoil", "jotai", "pinia",
    # Testing
    "jest", "playwright", "cypress", "testing", "vitest", "mocha", "rspec",
    # DevOps / Cloud
    "docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "git", "github",
    "gitlab", "linux", "terraform", "ansible", "helm",
    # APIs / Protocols
    "graphql", "rest", "grpc", "websocket", "trpc",
    # Other
    "agile", "scrum", "eslint", "figma", "storybook",
}

# ── Experience inference ───────────────────────────────────────────────────────
# Maps level keywords / soft phrases found in job text → estimated years.
# All signals are collected and the HIGHEST is used.

LEVEL_KEYWORD_YEARS: list[tuple[list[str], float]] = [
    (["intern", "internship", "trainee"],                            0.5),
    (["entry level", "entry-level", "entry"],                        1.0),
    (["junior", "jr.", "jr "],                                       2.0),
    (["mid level", "mid-level", "midlevel", "intermediate"],         3.0),
    (["senior", "sr.", "sr "],                                       5.0),
    (["lead", "tech lead", "team lead", "engineering lead"],         6.0),
    (["principal", "staff engineer", "staff software", "architect"], 7.0),
]

SOFT_EXPERIENCE_PHRASES: list[tuple[list[str], float]] = [
    (["some experience", "basic experience", "exposure to"],         1.5),
    (["hands-on experience", "solid experience", "good experience",
      "proven experience", "strong background"],                     3.0),
    (["several years", "multiple years", "number of years"],         4.0),
    (["extensive experience", "extensive background",
      "deep experience", "deep knowledge"],                          5.0),
]

# ── Known companies ───────────────────────────────────────────────────────────
# Companies in this set receive a higher company score.

KNOWN_COMPANIES: set[str] = {
    "google", "microsoft", "amazon", "meta", "apple", "netflix", "shopify",
    "stripe", "twilio", "github", "gitlab", "atlassian", "hubspot", "salesforce",
    "datadog", "vercel", "supabase", "linear", "notion", "figma", "canva",
    "cloudflare", "hashicorp", "elastic", "mongodb", "confluent", "dbt",
}
