"""
Thin wrapper around the Instagram Graph API's content-publishing flow:
create a media container, then publish it. Carousels create one child
container per image first, then a parent carousel container referencing them.

Requires IG_USER_ID + IG_ACCESS_TOKEN (from a Business/Creator account
linked to a Facebook Page, with the instagram_business_content_publish
permission approved - see README for the prerequisite setup, which is
the one piece of this whole system that's genuinely outside our control).
"""

import time

import httpx

from config import Config


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{Config.GRAPH_API_VERSION}/{path}"


def _post(path: str, params: dict) -> dict:
    Config.require("IG_USER_ID", "IG_ACCESS_TOKEN")
    params = {**params, "access_token": Config.IG_ACCESS_TOKEN}
    with httpx.Client(timeout=30) as client:
        resp = client.post(_graph_url(path), params=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"Instagram API error ({resp.status_code}): {resp.text}")
        return resp.json()


def _get(path: str, params: dict) -> dict:
    Config.require("IG_USER_ID", "IG_ACCESS_TOKEN")
    params = {**params, "access_token": Config.IG_ACCESS_TOKEN}
    with httpx.Client(timeout=30) as client:
        resp = client.get(_graph_url(path), params=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"Instagram API error ({resp.status_code}): {resp.text}")
        return resp.json()


def create_image_container(image_url: str, caption: str = "", is_carousel_item: bool = False) -> str:
    """Create a single-image media container. Returns the container ID."""
    params = {"image_url": image_url}
    if is_carousel_item:
        params["is_carousel_item"] = "true"
    else:
        params["caption"] = caption
    result = _post(f"{Config.IG_USER_ID}/media", params)
    return result["id"]


def create_carousel_container(child_container_ids: list[str], caption: str) -> str:
    """Create the parent carousel container referencing already-created child containers."""
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_container_ids),
        "caption": caption,
    }
    result = _post(f"{Config.IG_USER_ID}/media", params)
    return result["id"]


def wait_for_container_ready(container_id: str, timeout_seconds: int = 60, poll_interval: int = 3) -> None:
    """Carousel children need a moment to finish processing before the parent
    container can reference them. Poll status_code until FINISHED."""
    elapsed = 0
    while elapsed < timeout_seconds:
        result = _get(container_id, {"fields": "status_code"})
        status = result.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} failed processing: {result}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"Container {container_id} did not finish processing within {timeout_seconds}s")


def publish_container(container_id: str) -> str:
    """Publish a ready container. Returns the published media ID."""
    result = _post(f"{Config.IG_USER_ID}/media_publish", {"creation_id": container_id})
    return result["id"]


def publish_carousel(image_urls: list[str], caption: str) -> str:
    """
    Full flow for a carousel post: create each child container, wait for them
    to process, create the parent carousel container, then publish it.
    Returns the published media ID.
    """
    child_ids = [create_image_container(url, is_carousel_item=True) for url in image_urls]
    for child_id in child_ids:
        wait_for_container_ready(child_id)

    carousel_id = create_carousel_container(child_ids, caption)
    wait_for_container_ready(carousel_id)
    return publish_container(carousel_id)


def get_media_insights(media_id: str, metrics: list[str] | None = None) -> dict:
    """
    Pull performance metrics for a published post. Default metrics cover
    what Phase 3's feedback loop needs: reach, saves, shares, engagement.
    """
    if metrics is None:
        metrics = ["reach", "saved", "shares", "likes", "comments", "total_interactions"]
    result = _get(f"{media_id}/insights", {"metric": ",".join(metrics), "metric_type": "total_value"})

    values = {}
    for entry in result.get("data", []):
        name = entry.get("name")
        total = entry.get("total_value", {}).get("value")
        values[name] = total
    return values
