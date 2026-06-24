"""
Instagram's API requires images to live at a public URL at publish time.
Rather than pay for S3/Cloudinary, rendered carousel images get committed
into this repo and served straight from raw.githubusercontent.com - free,
no extra account, no extra credential to manage.
"""

import re

from config import Config

MEDIA_ROOT = "media"


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:50] or "post"


def raw_url(relative_path: str) -> str:
    """Build the public raw.githubusercontent.com URL for a file already
    committed and pushed to the repo at `relative_path`."""
    Config.require("GITHUB_OWNER", "GITHUB_REPO")
    relative_path = relative_path.replace("\\", "/").lstrip("./")
    return (
        f"https://raw.githubusercontent.com/{Config.GITHUB_OWNER}/{Config.GITHUB_REPO}"
        f"/{Config.GITHUB_BRANCH}/{relative_path}"
    )
