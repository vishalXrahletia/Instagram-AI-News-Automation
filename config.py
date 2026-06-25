"""
Central config. Everything is read from environment variables so the same
code runs locally (via a .env file) and in GitHub Actions (via repo secrets).
Nothing here is a secret itself - see .env.example for what to fill in.
"""

import os


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    # --- Phase control -------------------------------------------------
    # 1 = draft only, 2 = + scheduled publishing, 3 = + analytics feedback,
    # 4 = + semi-autonomous posting for trusted templates.
    PHASE = int(os.environ.get("PHASE", "1"))

    # --- Gemini (free tier - generativelanguage.googleapis.com) ----------
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # --- Airtable --------------------------------------------------------
    AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
    AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
    AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Drafts")

    # --- Instagram (Graph API) -------------------------------------------
    IG_USER_ID = os.environ.get("IG_USER_ID", "")
    IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
    GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")

    # --- Media hosting (for Instagram's "must be a public URL" rule) ----
    # Images get committed into this repo and served from raw.githubusercontent.com
    # so you don't need S3/Cloudinary. Set these to your actual repo.
    GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "")
    GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
    GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

    # --- Brand / voice ----------------------------------------------------
    PAGE_NAME = os.environ.get("PAGE_NAME", "your page")
    STORIES_PER_RUN = int(os.environ.get("STORIES_PER_RUN", "8"))

    # --- Phase 4: trusted templates allowed to auto-publish --------------
    TRUSTED_TEMPLATES = _env_list(
        "TRUSTED_TEMPLATES",
        "3 AI updates today,1 tool + 1 use case + 1 takeaway",
    )

    @classmethod
    def require(cls, *names: str) -> None:
        """Raise a clear error if required settings are missing, instead of
        failing deep inside an HTTP call with a confusing message."""
        missing = [n for n in names if not getattr(cls, n, None)]
        if missing:
            raise RuntimeError(
                f"Missing required config: {', '.join(missing)}. "
                f"Set these as environment variables or GitHub Actions secrets."
            )
