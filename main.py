"""
CLI entrypoint. The GitHub Actions workflow calls each stage separately so a
git commit+push can happen between 'render' and 'publish' (Instagram needs a
real public URL, which only exists after the push).

Usage:
    python3 main.py discover    # Phase 1+: fetch news, draft, queue in Airtable
    python3 main.py roundup     # Phase 4: auto-generate + auto-schedule trusted roundup
    python3 main.py render      # Phase 2+: render images for Approved/Scheduled records
    python3 main.py publish     # Phase 2+: publish queued posts (run AFTER committing media/)
    python3 main.py analytics   # Phase 3+: refresh insights/scores on posted content
    python3 main.py all         # run every stage in the correct order (for local testing)
"""

import sys

import pipeline

STAGES = {
    "discover": pipeline.run_discover,
    "roundup": pipeline.run_roundup,
    "render": pipeline.run_render,
    "publish": pipeline.run_publish,
    "analytics": pipeline.run_analytics,
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {*STAGES.keys(), "all"}:
        print(__doc__)
        sys.exit(1)

    stage = sys.argv[1]
    if stage == "all":
        for name, fn in STAGES.items():
            print(f"\n=== {name} ===")
            fn()
    else:
        STAGES[stage]()


if __name__ == "__main__":
    main()
