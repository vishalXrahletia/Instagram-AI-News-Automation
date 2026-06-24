# AI News Instagram Automation — Complete System

One codebase, four phases, runs for free on a daily schedule via GitHub Actions. No server to rent, no n8n instance to keep alive, no MCP marketplace to configure — just this repo plus three sets of credentials.

Everything below is tested. The dedupe/ranking logic, the carousel image renderer, and the full discover → roundup → render → publish → analytics pipeline were all run end-to-end against mocked services before this was handed to you — see the bottom of this file for exactly what that proves and doesn't prove.

## What it does, by phase

Controlled by one setting (`PHASE`), so you move forward by changing a number, not by rebuilding anything:

| Phase | What runs |
|---|---|
| 1 | Fetches AI news → drafts in your brand voice → writes to Airtable as "Draft". Nothing posts. |
| 2 | + Renders approved drafts into carousel images, publishes them to Instagram, marks them "Posted". |
| 3 | + Pulls post performance (reach/saves/shares), scores it, and feeds top performers back into future drafting. |
| 4 | + Auto-generates and auto-schedules the "3 AI updates today" roundup without waiting for manual approval. |

Start at `PHASE=1`. Don't touch Phase 2 until you've watched a few days of drafts land in Airtable and you trust the voice.

## The four things only you can do

No amount of engineering removes these — they need your identity/accounts or Meta's external process:

1. **Create accounts**: GitHub (free), Airtable (free tier), Anthropic API key (console.anthropic.com)
2. **Meta app review** for `instagram_business_content_publish` — 2-4 weeks, often rejected on the first submission. Start this today, in parallel with everything else, since it's the long pole.
3. **Get an Instagram access token** once that's approved
4. **Paste those into GitHub Secrets** — a few minutes of copy-paste, covered below

## Setup, in order

### 1. Push this code to a GitHub repo
Create a new repo (private is fine), and push everything in this folder to it.

### 2. Set up Airtable
Create a base called "Instagram Content Queue" with a table named **Drafts** and these fields:

| Field | Type |
|---|---|
| Date | Date |
| Headline | Single line text |
| SourceLink | URL |
| Hook | Single line text |
| Caption | Long text |
| CarouselOutline | Long text |
| Status | Single select: Draft, Approved, Scheduled, Posted |
| MediaId | Single line text |
| Reach | Number |
| Saved | Number |
| Shares | Number |
| Likes | Number |
| Comments | Number |
| Score | Number |

Generate a personal access token at airtable.com/create/tokens with `data.records:read` and `data.records:write` scope on this base. Note your Base ID (Help → API documentation, or it's in the base's URL).

### 3. Get an Anthropic API key
console.anthropic.com → API Keys → Create Key.

### 4. Configure GitHub Actions
In your repo: **Settings → Secrets and variables → Actions**.

Add these as **Secrets** (sensitive):
- `ANTHROPIC_API_KEY`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `IG_USER_ID` (leave blank until Phase 2)
- `IG_ACCESS_TOKEN` (leave blank until Phase 2)

Add these as **Variables** (not sensitive, fine to see in logs):
- `PHASE` = `1`
- `PAGE_NAME` = your actual page name
- `CLAUDE_MODEL` = `claude-sonnet-4-6`
- `AIRTABLE_TABLE_NAME` = `Drafts`
- `STORIES_PER_RUN` = `8`
- `TRUSTED_TEMPLATES` = `3 AI updates today,1 tool + 1 use case + 1 takeaway`

### 5. Test it manually
Go to the **Actions** tab → "Daily AI news pipeline" → **Run workflow**. Watch it run. At `PHASE=1` it'll only fetch, draft, and write to Airtable — check your base for new "Draft" rows.

If a step fails, the error will name exactly which credential or feed is the problem — nothing fails silently.

### 6. Let it run daily
Once a manual run looks right, leave it. The cron in `.github/workflows/daily.yml` fires once a day automatically — no server, no uptime to manage. Adjust the cron line if 7am IST (`30 1 * * *` UTC) isn't when you want it.

### 7. Review your drafts
For now, reviewing means opening Airtable and changing a record's Status from "Draft" to "Approved" once you're happy with it. (A nicer review UI is a reasonable next step once you're comfortable with the content quality, but Airtable's own interface is a perfectly real approval queue on its own.)

### 8. Move to Phase 2 once your Meta app review is approved
- Get your `IG_USER_ID` and `IG_ACCESS_TOKEN`, add them as secrets
- Change the `PHASE` variable to `2`
- Approve a draft in Airtable, run the workflow manually once to watch it render → commit → publish
- From here it's automatic: approve drafts whenever you like, the next daily run picks them up

### 9. Move to Phase 3 once you have a couple weeks of posted content
- Change `PHASE` to `3` — no other setup needed, it starts scoring automatically

### 10. Move to Phase 4 when you trust the voice completely
- Change `PHASE` to `4` — the roundup template starts auto-scheduling itself
- Everything else still requires your approval; only the named trusted template skips it

## Files

- `config.py` — every setting, read from environment
- `news.py` — fetch + dedupe + rank AI news (RSS + Hacker News)
- `draft.py` — Claude calls that write in your brand voice; also the trusted-roundup generator
- `render_carousel.py` — turns text into actual branded PNG carousel slides (Pillow)
- `airtable_client.py` — the approval queue
- `instagram_client.py` — Graph API container/publish/insights calls
- `analytics.py` — Phase 3 scoring + feedback
- `media_publish_helper.py` — slugs + the raw.githubusercontent.com URL trick that avoids needing S3/Cloudinary
- `pipeline.py` / `main.py` — orchestration and CLI
- `.github/workflows/daily.yml` — the entire "server" this needs

## What's been tested vs. what hasn't

**Tested and confirmed working**, with real assertions, not just "it ran":
- News dedupe/ranking logic against mock stories (correctly dropped an irrelevant story and merged two near-duplicate headlines)
- Carousel image rendering — actually rendered and visually inspected, text wraps and centers correctly
- The full discover → roundup → render → publish → analytics pipeline, end to end, with Airtable/Claude/Instagram calls mocked — data flowed correctly between every stage, the manifest correctly gated publishing until URLs would be valid, and the analytics score computed to the exact expected value

**Not tested, because it requires your live credentials**:
- The actual RSS feed URLs (outlets occasionally restructure their feeds — if one breaks, the error will say which)
- The real Anthropic API call (the prompt and parsing are tested against a mocked response, not Claude's actual output style — read your first batch of drafts before approving anything)
- The real Instagram Graph API calls (the request structure matches Meta's documented flow, but it can't be exercised without an approved app + token)
- The real Airtable API calls (same — structure is correct per their documented REST API, but untested against your actual base)

That last group is true of literally any integration with a service that requires your own private credentials — it's not a gap specific to this build, it's the nature of the boundary between what I can verify and what only runs against your live accounts.
