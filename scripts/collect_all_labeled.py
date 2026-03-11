"""
Discover all labeled screenshots and run verification for each via the API.
Writes a combined JSON file of armor pieces to data/collected/<output_filename>.

Requires the API (and task container) to be running. Run from repo root:
  python scripts/collect_all_labeled.py <output_filename>
  python scripts/collect_all_labeled.py run1.json

Uses API_BASE_URL or VITE_API_BASE_URL env, or --api-url; default http://localhost:8000.
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import urllib.request
    import urllib.error
    import urllib.parse
except ImportError:
    urllib = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELED_SUBDIRS = ("labeled/screenshots/regular", "labeled/screenshots/blueprint")
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 300
REQUEST_TIMEOUT_SEC = 120


def get_api_base_url(args_api_url: str | None) -> str:
    import os

    if args_api_url:
        return args_api_url.rstrip("/")
    base = os.environ.get("API_BASE_URL") or os.environ.get("VITE_API_BASE_URL")
    if base:
        return base.rstrip("/")
    return "http://localhost:8000"


def list_labeled_with_origin(base_url: str, timeout: int = REQUEST_TIMEOUT_SEC) -> list[tuple[str, str]]:
    """Return [(subdir, filename), ...] for all labeled screenshots that have a .txt origin."""
    out: list[tuple[str, str]] = []
    for subdir in LABELED_SUBDIRS:
        url = f"{base_url}/api/extract/screenshots?subdir={urllib.parse.quote(subdir)}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        filenames = data.get("filenames") or []
        has_origin = data.get("has_origin") or []
        for name in has_origin:
            if name in filenames:
                out.append((subdir, name))
    return sorted(out, key=lambda x: (x[0], x[1]))


def start_verify(base_url: str, filename: str, subdir: str, timeout: int = REQUEST_TIMEOUT_SEC) -> str:
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


def poll_task(base_url: str, task_id: str, timeout: int = 60) -> dict:
    """Poll GET /api/tasks/{task_id} until completed or failed; return full status dict."""
    url = f"{base_url}/api/tasks/{task_id}"
    start = time.monotonic()
    while True:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        status = data.get("status", "")
        if status in ("completed", "failed", "cancelled", "not_found"):
            return data
        if time.monotonic() - start > POLL_TIMEOUT_SEC:
            return {**data, "status": "failed", "error": "Poll timeout"}
        time.sleep(POLL_INTERVAL_SEC)


def format_piece_summary(piece: dict) -> str:
    """One-line summary of armor set, level, and stats for progress output."""
    name = piece.get("armor_set", "?")
    cur = piece.get("current_level", "?")
    mx = piece.get("max_level", "?")
    stats = piece.copy()
    for k in ("id", "armor_set", "armor_type", "current_level", "max_level"):
        stats.pop(k, None)
    stat_parts = [f"{k}:{v}" for k, v in sorted(stats.items()) if isinstance(v, (int, float))]
    stats_str = " ".join(stat_parts[:8])
    if len(stat_parts) > 8:
        stats_str += f" (+{len(stat_parts) - 8} more)"
    return f"{name} L{cur}/{mx}  {stats_str}"


def verification_result_to_piece(
    subdir: str, filename: str, result: dict
) -> dict | None:
    """Map verification result to one armor piece dict, or None if failed."""
    if result.get("status") != "completed":
        return None
    results = result.get("results") or {}
    if results.get("error"):
        return None
    armor_set = results.get("armor_set")
    current_level = results.get("current_level")
    max_level = results.get("max_level")
    stats = results.get("stats") or {}
    if armor_set is None:
        return None
    piece_id = f"{subdir.replace('/', '_')}_{Path(filename).stem}"
    piece = {
        "id": piece_id,
        "armor_set": armor_set,
        "armor_type": "unknown",
        "current_level": current_level if current_level is not None else 1,
        "max_level": max_level if max_level is not None else 16,
        **{k: v for k, v in stats.items() if isinstance(v, (int, float))},
    }
    return piece


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run verification on all labeled screenshots and save to data/collected/<file>."
    )
    parser.add_argument(
        "output_filename",
        help="Output filename (e.g. run1.json). Written to data/collected/<output_filename>.",
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
        help=f"Request timeout in seconds (default: {REQUEST_TIMEOUT_SEC})",
    )
    args = parser.parse_args()

    if urllib is None:
        print("urllib required", file=sys.stderr)
        return 1

    base_url = get_api_base_url(args.api_url)
    out_path = REPO_ROOT / "data" / "collected" / args.output_filename
    if not out_path.suffix.lower() == ".json":
        out_path = out_path.with_suffix(".json")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    timeout_sec = max(10, args.timeout)
    print(f"Listing labeled screenshots at {base_url} (timeout={timeout_sec}s) ...", flush=True)
    try:
        items = list_labeled_with_origin(base_url, timeout=timeout_sec)
    except TimeoutError:
        print(
            f"Request timed out after {timeout_sec}s. Is the API running at {base_url}?",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as e:
        print(f"Cannot reach API at {base_url}: {e}", file=sys.stderr)
        return 1

    if not items:
        print("No labeled screenshots with saved origin found.", file=sys.stderr)
        with open(out_path, "w") as f:
            json.dump([], f, indent=2)
        print(f"Wrote empty list to {out_path}")
        return 0

    print(f"Found {len(items)} screenshot(s). Verifying...")
    pieces: list[dict] = []
    failed = 0
    for i, (subdir, filename) in enumerate(items, 1):
        print(f"  [{i}/{len(items)}] {subdir}/{filename} ...", end=" ", flush=True)
        try:
            task_id = start_verify(base_url, filename, subdir, timeout=timeout_sec)
            status_data = poll_task(base_url, task_id, timeout=timeout_sec)
            piece = verification_result_to_piece(subdir, filename, status_data)
            if piece:
                pieces.append(piece)
                print("ok  ", format_piece_summary(piece))
            else:
                failed += 1
                err = (status_data.get("results") or {}).get("error") or status_data.get("error") or "failed"
                print(f"skip ({err})")
        except TimeoutError:
            failed += 1
            print("error: request timed out")
            continue
        except Exception as e:
            failed += 1
            print(f"error: {e}")
            continue

    with open(out_path, "w") as f:
        json.dump(pieces, f, indent=2)
    print(f"Wrote {len(pieces)} piece(s) to {out_path}")
    if failed:
        print(f"Skipped {failed} failed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
