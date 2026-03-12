"""Automated armor screenshot collection: move mouse to grid cells, capture, verify, save.

Run from repo root: python3 scripts/collect_armor_screenshots.py

Requires API and task containers running for verification. Screenshots are written to
data/labeled/screenshots/regular/ and data/labeled/screenshots/blueprint/ with unique
filenames. Collected armor data (with location) is saved to data/collected/armor_<output_folder>.json.

Origin is the top-left of the first armor card in the grid. It is written to each
screenshot's .txt and used by the task container (verify_card / extract_regions) to
crop and analyze the card; set it with o so cropping is correct.

Config (optional): JSON at scripts/collect_armor_screenshots_config.json or
data/collect_armor_screenshots_config.json with:
  origin_x, origin_y, step_x, step_y, next_page_x, next_page_y
Keys o, j, p set origin, step, and next-page at runtime. For j, move mouse to the
cell one column right and one row down from origin, then press j.

API base URL: env API_BASE_URL or VITE_API_BASE_URL, else http://localhost:8000
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import urllib.request
    import urllib.error
    import urllib.parse
except ImportError:
    urllib = None  # type: ignore

from pynput import keyboard

# Repo root for data paths
REPO_ROOT = Path(__file__).resolve().parent.parent
LABELED_SCREENSHOTS = REPO_ROOT / "data" / "labeled" / "screenshots"
DATA_COLLECTED = REPO_ROOT / "data" / "collected"
CONFIG_NAMES = [
    REPO_ROOT / "scripts" / "collect_armor_screenshots_config.json",
    REPO_ROOT / "data" / "collect_armor_screenshots_config.json",
]

# Filter UI positions: (filter_button_x, filter_button_y), then armor_type -> (x, y) for dropdown
REGULAR_FILTER_BUTTON = (225, 950)
REGULAR_FILTER_DROPDOWN = {
    "belt": (225, 540),
    "shoulder_pad": (225, 610),
    "mask": (225, 650),
    "hat": (225, 680),
    "greaves": (225, 720),
    "shield": (225, 750),
    "bracer": (225, 790),
}
BLUEPRINT_FILTER_BUTTON = (480, 120)
BLUEPRINT_FILTER_DROPDOWN = {
    "bracer": (480, 290),
    "shield": (480, 320),
    "greaves": (480, 360),
    "hat": (480, 390),
    "mask": (480, 430),
    "shoulder_pad": (480, 460),
    "belt": (480, 530),
}

LABELED_SUBDIRS = ("labeled/screenshots/regular", "labeled/screenshots/blueprint")
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 300
REQUEST_TIMEOUT_SEC = 120
MAX_PAGES_PER_TYPE = 50

MOVE_DELAY_S = 0.3
CLICK_DELAY_S = 0.5
FILTER_OPEN_DELAY_S = 0.4
FILTER_AFTER_SELECT_DELAY_S = 0.5


def _ensure_repo_path():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def load_config():
    """Load optional config with origin, step, next_page. Returns dict or None."""
    for p in CONFIG_NAMES:
        if p.is_file():
            try:
                with open(p) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
    return None


def get_api_base_url() -> str:
    base = os.environ.get("API_BASE_URL") or os.environ.get("VITE_API_BASE_URL")
    if base:
        return base.rstrip("/")
    return "http://localhost:8000"


def start_verify(base_url: str, filename: str, subdir: str) -> str:
    """POST /api/extract/verify; return task_id."""
    url = f"{base_url}/api/extract/verify"
    body = json.dumps({"filename": filename, "subdir": subdir}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
        data = json.loads(resp.read().decode())
    return data["task_id"]


def poll_task(base_url: str, task_id: str) -> dict:
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
        if time.monotonic() - start > POLL_TIMEOUT_SEC:
            return {**data, "status": "failed", "error": "Poll timeout"}
        time.sleep(POLL_INTERVAL_SEC)


def is_same_card(a: dict | None, b: dict | None) -> bool:
    """True if two verification results represent the same card (duplicate). Level can be unreadable."""
    if a is None or b is None:
        return False
    if a.get("armor_set") != b.get("armor_set"):
        return False
    if a.get("stats") != b.get("stats"):
        return False
    la, lb = a.get("current_level"), b.get("current_level")
    if la is not None and lb is not None and la != lb:
        return False
    return True


def select_armor_filter(pyautogui, blueprint_mode: bool, armor_type: str) -> None:
    """Click filter button, then the dropdown position for the armor type. Waits for dropdown."""
    if blueprint_mode:
        btn = BLUEPRINT_FILTER_BUTTON
        dropdown = BLUEPRINT_FILTER_DROPDOWN
    else:
        btn = REGULAR_FILTER_BUTTON
        dropdown = REGULAR_FILTER_DROPDOWN
    pos = dropdown.get(armor_type)
    if not pos:
        return
    pyautogui.moveTo(btn[0], btn[1])
    time.sleep(MOVE_DELAY_S)
    pyautogui.click()
    time.sleep(FILTER_OPEN_DELAY_S)
    pyautogui.moveTo(pos[0], pos[1])
    time.sleep(MOVE_DELAY_S)
    pyautogui.click()
    time.sleep(FILTER_AFTER_SELECT_DELAY_S)


# --- Page iteration: full grid per page ---


class _Page:
    """Iterate (row, col) over a page. 1-based. Optional start_col/start_row skip cells (e.g. first-page offset)."""

    def __init__(self, num_col: int, num_row: int, start_col: int = 1, start_row: int = 1):
        self.num_col = num_col
        self.num_row = num_row
        self.start_col = start_col
        self.start_row = start_row

    def __iter__(self):
        self.cur_row = self.start_row
        self.cur_col = self.start_col
        return self

    def __next__(self):
        if self.cur_row > self.num_row:
            raise StopIteration
        position = (self.cur_row, self.cur_col)
        if self.cur_col == self.num_col:
            self.cur_col = 1
            self.cur_row += 1
        else:
            self.cur_col += 1
        return position


def capture_primary_monitor(save_path: Path) -> None:
    """Capture the primary monitor (mss index 1) and save as PNG to save_path."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        mon = sct.monitors[1]
        shot = sct.grab(mon)
        img = Image.frombytes(
            "RGB",
            (shot.width, shot.height),
            shot.bgra,
            "raw",
            "BGRX",
        )
        img.save(save_path)


def _input_int(prompt: str, default: int | None = None) -> int:
    while True:
        s = input(prompt).strip()
        if default is not None and s == "":
            return default
        try:
            return int(s)
        except ValueError:
            print("Enter an integer.")


def run_full_automation(
    config_state: dict, output_folder: str, offset: int, api_base_url: str
) -> None:
    """Run all modes and armor types: filter select, capture, verify, duplicate detection, save JSON."""
    _ensure_repo_path()
    import pyautogui
    from shared.armor_constants import ARMOR_TYPES

    origin = config_state.get("origin")
    step = config_state.get("step")
    next_page_pos = config_state.get("next_page_pos")
    if origin is None or step is None:
        print("Missing origin or step. Set via config or press o; set step in config.")
        return
    if next_page_pos is None:
        print("Next-page position not set. Set via config or press p.")
        return

    DATA_COLLECTED.mkdir(parents=True, exist_ok=True)
    collected: list[dict] = []
    origin_x, origin_y = origin
    step_x, step_y = step

    for blueprint_mode in (False, True):
        mode_label = "blueprint" if blueprint_mode else "regular"
        subdir = LABELED_SUBDIRS[1] if blueprint_mode else LABELED_SUBDIRS[0]
        out_dir = LABELED_SCREENSHOTS / mode_label
        out_dir.mkdir(parents=True, exist_ok=True)
        num_col = 4 if blueprint_mode else 5
        num_row = 6 if blueprint_mode else 3
        first_page_col_start = 1 + (offset % num_col)
        first_page_row_start = 1 + (offset // num_col)
        global_index = 0

        for armor_type in ARMOR_TYPES:
            select_armor_filter(pyautogui, blueprint_mode, armor_type)
            previous_result: dict | None = None
            type_done = False

            for page_num in range(1, MAX_PAGES_PER_TYPE + 1):
                if type_done:
                    break
                if page_num == 1 and offset > 0:
                    page = _Page(num_col, num_row, first_page_col_start, first_page_row_start)
                else:
                    page = _Page(num_col, num_row)
                for row, col in page:
                    x = origin_x + (col - 1) * step_x
                    y = origin_y + (row - 1) * step_y
                    pyautogui.moveTo(x, y)
                    time.sleep(MOVE_DELAY_S)

                    base_name = f"{output_folder}_{armor_type}_p{page_num}_r{row}_c{col}_{global_index:04d}"
                    filename = f"{base_name}.png"
                    png_path = out_dir / filename
                    txt_path = out_dir / f"{base_name}.txt"
                    try:
                        capture_primary_monitor(png_path)
                        txt_path.write_text(f"{x} {y}\n")
                    except Exception as e:
                        print(f"Error saving {base_name}: {e}", file=sys.stderr)
                        global_index += 1
                        continue

                    task_id = start_verify(api_base_url, filename, subdir)
                    result = poll_task(api_base_url, task_id)
                    results = result.get("results") or {}
                    status = result.get("status", "")
                    if status == "failed":
                        err = result.get("error", "Unknown error")
                        print(f"Verify failed {base_name}: {err}", file=sys.stderr)
                        entry = {
                            "filename": filename,
                            "subdir": subdir,
                            "armor_type": armor_type,
                            "mode": mode_label,
                            "page": page_num,
                            "row": row,
                            "col": col,
                            "origin_x": x,
                            "origin_y": y,
                            "armor_set": None,
                            "current_level": None,
                            "max_level": None,
                            "stats": {},
                            "error": err,
                        }
                        collected.append(entry)
                        previous_result = None
                        global_index += 1
                        continue

                    cur_result = {
                        "armor_set": results.get("armor_set"),
                        "current_level": results.get("current_level"),
                        "max_level": results.get("max_level"),
                        "stats": results.get("stats") or {},
                        "error": results.get("error"),
                    }
                    if previous_result is not None and is_same_card(previous_result, cur_result):
                        print(f"Duplicate at {base_name}, stopping {armor_type} for {mode_label}.")
                        type_done = True
                        break

                    entry = {
                        "filename": filename,
                        "subdir": subdir,
                        "armor_type": armor_type,
                        "mode": mode_label,
                        "page": page_num,
                        "row": row,
                        "col": col,
                        "origin_x": x,
                        "origin_y": y,
                        "armor_set": cur_result.get("armor_set"),
                        "current_level": cur_result.get("current_level"),
                        "max_level": cur_result.get("max_level"),
                        "stats": cur_result.get("stats"),
                        "error": cur_result.get("error"),
                    }
                    collected.append(entry)
                    previous_result = cur_result
                    print(f"Saved {base_name} -> {cur_result.get('armor_set')} L{cur_result.get('current_level')}/{cur_result.get('max_level')}")
                    global_index += 1

                if type_done:
                    break
                if page_num < MAX_PAGES_PER_TYPE:
                    px, py = next_page_pos
                    pyautogui.moveTo(px, py)
                    time.sleep(MOVE_DELAY_S)
                    pyautogui.click()
                    time.sleep(CLICK_DELAY_S)

    out_json = DATA_COLLECTED / f"armor_{output_folder}.json"
    with open(out_json, "w") as f:
        json.dump(collected, f, indent=2)
    print(f"Collected {len(collected)} armor pieces -> {out_json.relative_to(REPO_ROOT)}")
    print("Automation finished.")


def main():
    _ensure_repo_path()
    from shared.armor_constants import ARMOR_TYPES

    if urllib is None:
        print("urllib required for API calls.", file=sys.stderr)
        sys.exit(1)

    cfg = load_config()
    config_state = {}
    if cfg:
        if "origin_x" in cfg and "origin_y" in cfg:
            config_state["origin"] = (int(cfg["origin_x"]), int(cfg["origin_y"]))
        if "step_x" in cfg and "step_y" in cfg:
            config_state["step"] = (int(cfg["step_x"]), int(cfg["step_y"]))
        if "next_page_x" in cfg and "next_page_y" in cfg:
            config_state["next_page_pos"] = (int(cfg["next_page_x"]), int(cfg["next_page_y"]))

    offset = _input_int("Offset (non-armor cells on first page, 0 or more) [0]: ", 0)
    if offset < 0:
        offset = 0
    output_folder = input("Output folder name (used for filenames and data/collected/armor_<name>.json) [armor_run]: ").strip()
    if not output_folder:
        output_folder = "armor_run"

    print()
    print("Keys: o = set origin, j = set step (mouse on cell 1 right + 1 down), p = set next-page, l = start. Ctrl+C = quit.")
    print(f"Armor types: {', '.join(ARMOR_TYPES)}")
    print(f"API: {get_api_base_url()}")
    print()

    with keyboard.Events() as events:
        for event in events:
            if not isinstance(event, keyboard.Events.Press):
                continue
            key = event.key
            c = getattr(key, "char", None)
            if c not in ("o", "j", "p", "l"):
                continue

            if c == "o":
                import pyautogui
                config_state["origin"] = pyautogui.position()
                print("Origin set.")
                continue
            if c == "j":
                import pyautogui
                origin = config_state.get("origin")
                if origin is None:
                    print("Set origin (o) first, then move to the cell one right and one down and press j.")
                    continue
                cur_x, cur_y = pyautogui.position()
                origin_x, origin_y = origin
                config_state["step"] = (cur_x - origin_x, cur_y - origin_y)
                print("Step set.")
                continue
            if c == "p":
                import pyautogui
                config_state["next_page_pos"] = pyautogui.position()
                print("Next-page set.")
                continue
            if c == "l":
                run_full_automation(config_state, output_folder, offset, get_api_base_url())
                continue


if __name__ == "__main__":
    main()
