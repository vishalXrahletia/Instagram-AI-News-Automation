"""
Turns raw news stories into Instagram-ready drafts (hook, caption, carousel
outline) in the "explained simply" brand voice, by calling the free-tier
Gemini API.
"""

import json

import httpx

from config import Config

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

VOICE_INSTRUCTIONS = """You are the writer for an Instagram page called "{page_name}",
positioned as "AI news explained simply" - not a repost account. Your voice: clear,
conversational, zero hype, explains WHY something matters in plain English, never just
restates a headline.

Banned words: "game-changing", "revolutionary", "insane", "mind-blowing", or any other hype word.
Always answer "so what does this mean for me" for a creator, freelancer, or small business
owner reading this - not just "what happened"."""


def _build_prompt(stories: list[dict], preferred_angles: list[str] | None = None) -> str:
    story_lines = []
    for i, s in enumerate(stories, start=1):
        story_lines.append(
            f"{i}. Title: {s['title']}\n   Source: {s['source']}\n   Link: {s['link']}\n   Summary: {s['summary']}"
        )
    stories_block = "\n\n".join(story_lines)

    bias_note = ""
    if preferred_angles:
        bias_note = (
            "\nNote: these angles/topics have performed well with this audience recently - "
            f"lean toward similar framing where it genuinely fits, but never force it onto a story "
            f"it doesn't suit: {', '.join(preferred_angles)}\n"
        )

    return f"""Here are today's top AI stories. For EACH story below, write Instagram content.
{bias_note}
For each story return:
- headline: the original headline
- source_link: the original link
- hook: a scroll-stopping hook, max 12 words, no hashtags
- caption: 60-90 words, plain conversational language, explain what happened and why it
  actually matters to creators, freelancers, or small business owners
- carousel: an array of exactly 5 short lines (max ~10 words each), one per carousel slide,
  building from hook to explanation to takeaway

Return ONLY a valid JSON array, nothing else, no markdown code fences, no commentary.
Structure:
[{{"headline":"...","source_link":"...","hook":"...","caption":"...","carousel":["...","...","...","...","..."]}}]

Stories:

{stories_block}"""


def _call_gemini(prompt: str, system: str) -> str:
    Config.require("GEMINI_API_KEY")
    url = GEMINI_URL_TEMPLATE.format(model=Config.GEMINI_MODEL)
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            url,
            headers={
                "x-goog-api-key": Config.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {
                    "maxOutputTokens": 3000,
                    "responseMimeType": "application/json",
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from e


def _parse_drafts(raw_text: str) -> list[dict]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    return json.loads(text)


def generate_drafts(stories: list[dict], preferred_angles: list[str] | None = None) -> list[dict]:
    """Call Gemini once with all stories batched together, return a list of
    draft dicts: headline, source_link, hook, caption, carousel (list[str])."""
    if not stories:
        return []

    system = VOICE_INSTRUCTIONS.format(page_name=Config.PAGE_NAME)
    prompt = _build_prompt(stories, preferred_angles=preferred_angles)
    raw_text = _call_gemini(prompt, system)

    try:
        return _parse_drafts(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Gemini's response wasn't valid JSON ({e}). First 300 chars: {raw_text[:300]}"
        )


def generate_roundup(stories: list[dict]) -> dict:
    """
    Generate ONE combined draft in the "3 AI updates today" trusted-template
    format: a single post covering exactly 3 stories, one slide each plus a
    closing takeaway slide. This is the only template Phase 4 is allowed to
    auto-publish without manual approval - see the operating playbook for why
    that boundary matters.
    """
    if len(stories) < 3:
        raise ValueError("Need at least 3 stories to build a roundup")

    top3 = stories[:3]
    story_lines = "\n\n".join(
        f"{i}. Title: {s['title']}\n   Source: {s['source']}\n   Summary: {s['summary']}"
        for i, s in enumerate(top3, start=1)
    )

    system = VOICE_INSTRUCTIONS.format(page_name=Config.PAGE_NAME)
    prompt = f"""Write ONE Instagram post in the "3 AI updates today" format covering exactly these 3 stories:

{story_lines}

Return ONLY valid JSON, no markdown fences, no commentary, structured as:
{{"headline":"3 AI updates today","source_link":"","hook":"a single scroll-stopping hook line for the whole roundup, max 10 words","caption":"60-90 words summarizing all 3 updates and why they matter together","carousel":["slide 1: update #1 in one short line","slide 2: update #2 in one short line","slide 3: update #3 in one short line","slide 4: one-line closing takeaway tying them together"]}}"""

    raw_text = _call_gemini(prompt, system)
    try:
        return _parse_drafts(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Gemini's roundup response wasn't valid JSON ({e}). First 300 chars: {raw_text[:300]}"
        )
