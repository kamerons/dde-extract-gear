"""Run box detector training via the API; when it reaches 100% test accuracy, shut down the machine.

Requires the API and task worker to be running (e.g. `python start.py start`). This script
starts a single training run (or attaches to one already in progress), polls until it
completes, then if accuracy_within_5px >= 1.0 (or stopped_early_100 is true), runs
`sudo shutdown -h now`. Only the shutdown command needs sudo; run the script as a normal user.
For unattended use, configure NOPASSWD for shutdown in sudoers, e.g.:

  %shutdown ALL=(ALL) NOPASSWD: /usr/sbin/shutdown

If a training task is already pending or processing (e.g. from the UI or a previous run),
the script attaches to that task instead of starting a new one, so the task is not cancelled.
Run only one instance of this script; if you run it again while one is already polling,
the second run will attach to the same task.

Usage:
  API_BASE_URL=http://localhost:8000 python scripts/run_training_until_100_and_shutdown.py

Environment:
  API_BASE_URL  Base URL for the API (default: http://localhost:8000)
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    base_url = (os.environ.get("API_BASE_URL") or os.environ.get("VITE_API_BASE_URL") or "").rstrip("/")
    if not base_url:
        base_url = "http://localhost:8000"

    task_id = None
    # Attach to existing training task if one is already running (avoids cancelling it)
    try:
        with urllib.request.urlopen(f"{base_url}/api/extract/training/current", timeout=10) as resp:
            data = json.loads(resp.read().decode())
            current_id = data.get("task_id") if isinstance(data, dict) else None
            if current_id:
                with urllib.request.urlopen(f"{base_url}/api/tasks/{current_id}", timeout=10) as status_resp:
                    status_data = json.loads(status_resp.read().decode())
                    status = status_data.get("status", "")
                    if status in ("pending", "processing"):
                        task_id = current_id
                        print(f"Attaching to existing training task {task_id}; polling until completed.")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass

    if not task_id:
        # Start a new training task
        req = urllib.request.Request(
            f"{base_url}/api/extract/training/start",
            data=json.dumps({"model_type": "box_detector"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            print(f"Failed to start training: {e}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as e:
            print(f"Invalid start response: {e}", file=sys.stderr)
            return 1
        task_id = body.get("task_id")
        if not task_id:
            print("Start response missing task_id", file=sys.stderr)
            return 1
        print(f"Started training task {task_id}; polling until completed.")

    # Poll until completed, failed, or cancelled
    while True:
        try:
            with urllib.request.urlopen(f"{base_url}/api/tasks/{task_id}", timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            print(f"Poll error: {e}", file=sys.stderr)
            time.sleep(10)
            continue
        status = data.get("status", "")
        if status == "completed":
            results = data.get("results") or {}
            acc = results.get("accuracy_within_5px")
            stopped_100 = results.get("stopped_early_100", False)
            if (acc is not None and acc >= 1.0) or stopped_100:
                print("100% test accuracy reached; shutting down.")
                subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
                return 0
            print("Training completed but accuracy was not 100%; not shutting down.")
            return 0
        if status in ("failed", "cancelled", "not_found"):
            print(f"Training ended with status: {status}", file=sys.stderr)
            if data.get("error"):
                print(data["error"], file=sys.stderr)
            return 1
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
