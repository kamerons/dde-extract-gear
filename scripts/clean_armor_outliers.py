#!/usr/bin/env python3
"""
Identify and remove extreme outliers from collected armor JSON.

Outliers (likely OCR or extraction errors):
- hero_hp > 99  (e.g. 291, 401, 681; plausible misread of 29, 40, 68)
- tower_hp > 99 (e.g. 501, 631, 372; plausible misread of 50, 63, 37)
- base < 10    (e.g. 0, 4, 6; plausible misread when digit lost or wrong)

Records with any of these are excluded from the cleaned output.
"""

import json
import sys
from pathlib import Path


def is_outlier(stat_name: str, value: int) -> bool:
    if stat_name == "hero_hp" and value > 99:
        return True
    if stat_name == "tower_hp" and value > 99:
        return True
    if stat_name == "base" and value < 10:
        return True
    return False


def record_has_outlier(record: dict) -> list[tuple[str, int]]:
    stats = record.get("stats") or {}
    out = []
    for stat, val in stats.items():
        if isinstance(val, (int, float)) and is_outlier(stat, int(val)):
            out.append((stat, int(val)))
    return out


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    path = repo / "data" / "collected" / "armor_run1.json"
    out_path = repo / "data" / "collected" / "armor_run1_cleaned.json"

    if not path.exists():
        print(f"Missing: {path}", file=sys.stderr)
        return 1

    with open(path) as f:
        records = json.load(f)

    with_outliers = []
    for r in records:
        bad = record_has_outlier(r)
        if bad:
            with_outliers.append((r, bad))

    if not with_outliers:
        print("No outlier records found.")
        return 0

    print("Outlier records (excluded from cleaned output):\n")
    for r, bad in with_outliers:
        fname = r.get("filename", "?")
        parts = [f"{stat}={val}" for stat, val in bad]
        print(f"  {fname}: {', '.join(parts)}")

    cleaned = [r for r in records if not record_has_outlier(r)]
    removed = len(records) - len(cleaned)
    print(f"\nRemoved {removed} record(s). {len(cleaned)} remaining.")

    with open(out_path, "w") as f:
        json.dump(cleaned, f, indent=2)

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
