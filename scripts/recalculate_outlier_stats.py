#!/usr/bin/env python3
"""
Recalculate stats for armor Run1 outlier records via the verification API.

Reads outlier filenames from data/collected/armor_run1_outliers.md, loads
data/collected/armor_run1.json, calls the API verify endpoint for each matching
record, and updates those records in place (stats, armor_set, current_level,
max_level, error). Writes the updated list back to armor_run1.json.

Requires the API (and task container) to be running. Run from repo root:
  python scripts/recalculate_outlier_stats.py
  python scripts/recalculate_outlier_stats.py --api-url http://localhost:8000
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import urllib.request
    import urllib.error
    import urllib.parse
except ImportError:
    urllib = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 300
REQUEST_TIMEOUT_SEC = 120


def _outlier_filenames_from_md(md_path: Path) -> set[str]:
    """Parse markdown and return set of outlier filenames (e.g. run1_belt_p1_r3_c5_0154.png)."""
    text = md_path.read_text()
    # Lines like: 1. `run1_belt_p1_r3_c5_0154.png`
    pattern = re.compile(r"^\d+\.\s*`([^`]+\.png)`", re.MULTILINE)
    return set(m.group(1) for m in pattern.finditer(text))


def _get_api_base_url(api_url: str | None) -> str:
    import os

    if api_url:
        return api_url.rstrip("/")
    base = os.environ.get("API_BASE_URL") or os.environ.get("VITE_API_BASE_URL")
    if base:
        return base.rstrip("/")
    return "http://localhost:8000"


def _start_verify(base_url: str, filename: str, subdir: str, timeout: int = REQUEST_TIMEOUT_SEC) -> str:
    """POST /api/extract/verify; return task_id."""
    url = f"{base_url}/api/extract/verify"
    body = json.dumps({"filename": filename, "subdir": subdir}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data["task_id"]


def _poll_task(base_url: str, task_id: str, timeout: int = POLL_TIMEOUT_SEC) -> dict:
    """Poll GET /api/tasks/{task_id} until completed or failed; return full status dict."""
    url = f"{base_url}/api/tasks/{task_id}"
    start = time.monotonic()
    while True:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode())
        status = data.get("status", "")
        if status in ("completed", "failed", "cancelled", "not_found"):
            return data
        if time.monotonic() - start > timeout:
            return {**data, "status": "failed", "error": "Poll timeout"}
        time.sleep(POLL_INTERVAL_SEC)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recalculate stats for armor_run1 outliers via the verification API."
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="API base URL (default: env API_BASE_URL or VITE_API_BASE_URL, else http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=REQUEST_TIMEOUT_SEC,
        help=f"Request and poll timeout in seconds (default: {REQUEST_TIMEOUT_SEC})",
    )
    args = parser.parse_args()

    if urllib is None:
        print("urllib required for API calls.", file=sys.stderr)
        return 1

    outliers_md = REPO_ROOT / "data" / "collected" / "armor_run1_outliers.md"
    armor_json = REPO_ROOT / "data" / "collected" / "armor_run1.json"

    if not outliers_md.exists():
        print(f"Missing: {outliers_md}", file=sys.stderr)
        return 1
    if not armor_json.exists():
        print(f"Missing: {armor_json}", file=sys.stderr)
        return 1

    outlier_filenames = _outlier_filenames_from_md(outliers_md)
    if not outlier_filenames:
        print("No outlier filenames parsed from markdown.", file=sys.stderr)
        return 1

    base_url = _get_api_base_url(args.api_url)
    timeout_sec = max(10, args.timeout)
    print(f"API: {base_url}")
    print(f"Outlier count: {len(outlier_filenames)}")

    with open(armor_json) as f:
        records = json.load(f)

    updated = 0
    for record in records:
        fname = record.get("filename")
        if fname not in outlier_filenames:
            continue
        subdir = record.get("subdir", "labeled/screenshots/regular")
        print(f"  Verifying {fname} ...", end=" ", flush=True)
        try:
            task_id = _start_verify(base_url, fname, subdir, timeout=timeout_sec)
            status_data = _poll_task(base_url, task_id, timeout=timeout_sec)
        except urllib.error.URLError as e:
            print(f"error: {e}", file=sys.stderr)
            continue
        except TimeoutError:
            print("error: request timed out", file=sys.stderr)
            continue
        results = status_data.get("results") or {}
        record["stats"] = results.get("stats") or {}
        record["armor_set"] = results.get("armor_set")
        record["current_level"] = results.get("current_level")
        record["max_level"] = results.get("max_level")
        record["error"] = results.get("error")
        updated += 1
        err = results.get("error")
        n_stats = len(record["stats"])
        print(f"ok  stats={n_stats}  error={err!r}")

    print(f"\nUpdated {updated} record(s).")

    with open(armor_json, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Wrote {armor_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
