#!/usr/bin/env python3
"""Scaffold an atomic daily note in the Obsidian vault (AI_Engineer/Daily_Notes).

Detects the current system date (Ubuntu/WSL local time), ensures the
``Daily_Notes/`` partition exists, and creates ``YYYY-MM-DD.md`` with the
standard YAML frontmatter + MOC backlink if it does not exist yet.
Idempotent: re-running never overwrites an existing note.

Usage:
    python3 src/daily_note.py                    # scaffold today's note
    python3 src/daily_note.py --date 2026-07-05  # scaffold a specific date
    python3 src/daily_note.py --vault /path/to/AI_Engineer
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

MOC_NAME = "Day3_Mini_NotebookLM"
BACKLINK = f"[[{MOC_NAME}|◀ Trở về Bản đồ Trung tâm]]"

TEMPLATE = """---
date: {date}
tags: [daily-note, learning-journey]
project: Day3 — Mini NotebookLM
---

{backlink}

# {date}

## Summary

-

## Changes

-
"""


def default_vault() -> Path:
    # Day3/src/daily_note.py → Project/AI_Engineer
    return Path(__file__).resolve().parents[2] / "AI_Engineer"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold an atomic daily note in the Obsidian vault."
    )
    parser.add_argument("--date", help="Override the system date (ISO YYYY-MM-DD)")
    parser.add_argument("--vault", type=Path, default=default_vault(),
                        help="Path to the Obsidian vault root")
    args = parser.parse_args(argv)

    date = args.date or dt.date.today().isoformat()
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        parser.error(f"--date must be ISO YYYY-MM-DD, got {date!r}")

    daily_dir = args.vault / "Daily_Notes"
    daily_dir.mkdir(parents=True, exist_ok=True)

    note = daily_dir / f"{date}.md"
    if note.exists():
        print(f"exists   {note}")
        return 0

    note.write_text(TEMPLATE.format(date=date, backlink=BACKLINK), encoding="utf-8")
    print(f"created  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
