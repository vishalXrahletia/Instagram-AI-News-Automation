"""
Phase 3: pulls Instagram insights for posted content, scores it, writes the
scores back to Airtable, and surfaces the best-performing angles so Phase 1's
drafting step can lean toward what's actually working.
"""

import airtable_client
import instagram_client

# Saves and shares are weighted higher than likes/comments because they're
# stronger signals of "this was worth keeping/spreading", which is what
# actually compounds page growth.
SCORE_WEIGHTS = {"saved": 3.0, "shares": 2.5, "comments": 1.5, "likes": 1.0}


def _compute_score(insights: dict) -> float:
    return round(sum(insights.get(metric, 0) * weight for metric, weight in SCORE_WEIGHTS.items()), 2)


def update_insights_for_posted() -> list[dict]:
    """
    For every record marked "Posted" that has a MediaId, pull fresh insights
    and write Reach/Saved/Shares/Likes/Comments/Score back to Airtable.
    Returns the list of updated records' fields for logging.
    """
    posted = airtable_client.list_records_by_status("Posted")
    updated = []

    for record in posted:
        fields = record.get("fields", {})
        media_id = fields.get("MediaId")
        if not media_id:
            continue

        try:
            insights = instagram_client.get_media_insights(media_id)
        except Exception as e:
            print(f"[analytics] WARNING: couldn't fetch insights for {media_id}: {e}")
            continue

        score = _compute_score(insights)
        update_fields = {
            "Reach": insights.get("reach", 0),
            "Saved": insights.get("saved", 0),
            "Shares": insights.get("shares", 0),
            "Likes": insights.get("likes", 0),
            "Comments": insights.get("comments", 0),
            "Score": score,
        }
        airtable_client.update_record(record["id"], update_fields)
        updated.append({"id": record["id"], "headline": fields.get("Headline"), **update_fields})

    return updated


def get_top_performing_angles(limit: int = 5) -> list[str]:
    """
    Return the Hooks of the highest-scoring posted records, to feed back into
    draft generation as "lean toward angles like these" hints. Returns an
    empty list gracefully if there isn't enough posted history yet - that's
    expected and fine in Phase 1/2, this only gets useful once Phase 3 has
    real data to learn from.
    """
    posted = airtable_client.list_records_by_status("Posted")
    scored = [r for r in posted if r.get("fields", {}).get("Score") is not None]
    scored.sort(key=lambda r: r["fields"]["Score"], reverse=True)
    return [r["fields"]["Hook"] for r in scored[:limit] if r["fields"].get("Hook")]
