"""
Thin wrapper around the Airtable REST API for the Drafts table.
No SDK dependency - just httpx, so there's one less thing to break.
"""

from datetime import date

import httpx

from config import Config

API_BASE = "https://api.airtable.com/v0"


def _headers() -> dict:
    Config.require("AIRTABLE_API_KEY", "AIRTABLE_BASE_ID")
    return {
        "Authorization": f"Bearer {Config.AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def _table_url() -> str:
    return f"{API_BASE}/{Config.AIRTABLE_BASE_ID}/{Config.AIRTABLE_TABLE_NAME}"


def create_draft_records(drafts: list[dict]) -> list[dict]:
    """
    Create one Airtable record per draft. Airtable allows max 10 records
    per request, so this batches automatically.
    Each draft dict should have: headline, source_link, hook, caption, carousel (list[str]).
    Returns the created Airtable records (with their record IDs).
    """
    today = date.today().isoformat()
    created = []

    with httpx.Client(timeout=30) as client:
        for i in range(0, len(drafts), 10):
            batch = drafts[i:i + 10]
            records = [{
                "fields": {
                    "Date": today,
                    "Headline": d.get("headline", ""),
                    "SourceLink": d.get("source_link", ""),
                    "Hook": d.get("hook", ""),
                    "Caption": d.get("caption", ""),
                    "CarouselOutline": "\n".join(d.get("carousel", [])),
                    "Status": "Draft",
                }
            } for d in batch]

            resp = client.post(_table_url(), headers=_headers(), json={"records": records})
            resp.raise_for_status()
            created.extend(resp.json().get("records", []))

    return created


def list_records_by_status(status: str) -> list[dict]:
    """Return all Airtable records whose Status field matches exactly."""
    records = []
    params = {"filterByFormula": f"{{Status}}='{status}'"}

    with httpx.Client(timeout=30) as client:
        offset = None
        while True:
            if offset:
                params["offset"] = offset
            resp = client.get(_table_url(), headers=_headers(), params=params)
            resp.raise_for_status()
            data = resp.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break

    return records


def update_record(record_id: str, fields: dict) -> dict:
    """Update one or more fields on a single record (e.g. Status, or analytics scores)."""
    with httpx.Client(timeout=30) as client:
        resp = client.patch(
            f"{_table_url()}/{record_id}",
            headers=_headers(),
            json={"fields": fields},
        )
        resp.raise_for_status()
        return resp.json()


def update_status(record_id: str, status: str) -> dict:
    return update_record(record_id, {"Status": status})
