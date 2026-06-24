"""
Daily pipeline orchestrator, split into stages so the GitHub Actions workflow
can commit newly rendered images between "render" and "publish" - Instagram
needs a real public URL at publish time, which only exists after a git push.

Each stage checks Config.PHASE itself and no-ops with a clear message if the
current phase doesn't call for it yet, so the workflow can always run every
stage and let PHASE control what actually happens.
"""

import json
import os
from datetime import date

import airtable_client
import analytics
import draft
import instagram_client
import news
import render_carousel
from config import Config
from media_publish_helper import MEDIA_ROOT, raw_url, slugify

MANIFEST_PATH = os.path.join(MEDIA_ROOT, "pending_publish.json")


def _load_manifest() -> list[dict]:
    if not os.path.exists(MANIFEST_PATH):
        return []
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def _save_manifest(entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def run_discover() -> None:
    """Phase 1+: fetch news, draft in brand voice, write to Airtable as Draft."""
    print(f"[discover] Phase {Config.PHASE}: fetching top {Config.STORIES_PER_RUN} AI stories...")
    stories = news.get_top_ai_stories(limit=Config.STORIES_PER_RUN)
    if not stories:
        print("[discover] No stories found - check feed URLs / network.")
        return
    print(f"[discover] Found {len(stories)} stories. Generating drafts...")

    preferred_angles = None
    if Config.PHASE >= 3:
        preferred_angles = analytics.get_top_performing_angles()
        if preferred_angles:
            print(f"[discover] Biasing drafts toward top-performing angles: {preferred_angles}")

    drafts = draft.generate_drafts(stories, preferred_angles=preferred_angles)
    created = airtable_client.create_draft_records(drafts)
    print(f"[discover] Created {len(created)} draft record(s) in Airtable, Status=Draft.")


def run_roundup() -> None:
    """Phase 4 only: auto-generate the trusted '3 AI updates today' roundup
    and queue it as Scheduled - the one content type allowed to skip manual
    approval, per the operating playbook's explicit boundary."""
    if Config.PHASE < 4:
        print("[roundup] Skipped - requires PHASE=4.")
        return
    if "3 AI updates today" not in Config.TRUSTED_TEMPLATES:
        print("[roundup] Skipped - '3 AI updates today' is not in TRUSTED_TEMPLATES.")
        return

    print("[roundup] Phase 4: generating trusted roundup template...")
    stories = news.get_top_ai_stories(limit=3)
    if len(stories) < 3:
        print("[roundup] Not enough stories today to build a roundup.")
        return

    draft_obj = draft.generate_roundup(stories)
    if isinstance(draft_obj, list):
        draft_obj = draft_obj[0]

    created = airtable_client.create_draft_records([draft_obj])
    if created:
        airtable_client.update_status(created[0]["id"], "Scheduled")
        print(f"[roundup] Auto-scheduled 1 trusted roundup post (record {created[0]['id']}).")


def run_render() -> None:
    """Phase 2+: render carousel images for any Approved/Scheduled record that
    doesn't have one queued yet. Writes a manifest for the publish stage -
    commit and push media/ to the repo BEFORE running 'publish', or the
    image URLs won't resolve yet."""
    if Config.PHASE < 2:
        print("[render] Skipped - requires PHASE>=2.")
        return

    manifest = _load_manifest()
    already_queued_ids = {entry["record_id"] for entry in manifest}

    candidates = (
        airtable_client.list_records_by_status("Approved")
        + airtable_client.list_records_by_status("Scheduled")
    )
    today_str = date.today().isoformat()
    new_entries = []

    for record in candidates:
        if record["id"] in already_queued_ids:
            continue
        fields = record.get("fields", {})
        hook = fields.get("Hook", "")
        carousel_text = fields.get("CarouselOutline", "")
        carousel_lines = [line for line in carousel_text.split("\n") if line.strip()]
        if not hook or not carousel_lines:
            print(f"[render] Skipping record {record['id']} - missing Hook or CarouselOutline.")
            continue

        slug = slugify(fields.get("Headline", record["id"]))
        output_dir = os.path.join(MEDIA_ROOT, today_str)
        image_paths = render_carousel.render_carousel(hook, carousel_lines, slug=slug, output_dir=output_dir)

        new_entries.append({
            "record_id": record["id"],
            "caption": fields.get("Caption", ""),
            "image_paths": image_paths,
        })
        print(f"[render] Rendered {len(image_paths)} slide(s) for record {record['id']} ({slug}).")

    if new_entries:
        _save_manifest(manifest + new_entries)
        print(f"[render] {len(new_entries)} new post(s) queued. Commit + push media/ before running 'publish'.")
    else:
        print("[render] Nothing new to render.")


def run_publish() -> None:
    """Phase 2+: publish anything in the manifest. Assumes the render stage's
    output has already been committed and pushed in a prior workflow step."""
    if Config.PHASE < 2:
        print("[publish] Skipped - requires PHASE>=2.")
        return

    manifest = _load_manifest()
    if not manifest:
        print("[publish] Nothing queued to publish.")
        return

    remaining = []
    for entry in manifest:
        record_id = entry["record_id"]
        try:
            urls = [raw_url(p) for p in entry["image_paths"]]
            media_id = instagram_client.publish_carousel(urls, entry["caption"])
            airtable_client.update_record(record_id, {"Status": "Posted", "MediaId": media_id})
            print(f"[publish] Published record {record_id} -> media {media_id}.")
        except Exception as e:
            print(f"[publish] FAILED to publish record {record_id}, will retry next run: {e}")
            remaining.append(entry)

    _save_manifest(remaining)


def run_analytics() -> None:
    """Phase 3+: refresh insights/scores on posted content."""
    if Config.PHASE < 3:
        print("[analytics] Skipped - requires PHASE>=3.")
        return
    updated = analytics.update_insights_for_posted()
    print(f"[analytics] Refreshed scores for {len(updated)} posted record(s).")
    for u in updated:
        print(f"  - {u['headline']}: score={u['Score']} reach={u['Reach']} saved={u['Saved']}")
