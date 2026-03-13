"""Automated armor screenshot collection: move mouse to grid cells, capture, verify, save.

Run from repo root: python3 scripts/collect_armor_screenshots.py

Requires API and task containers running for verification. Screenshots are written to
data/labeled/screenshots/regular/ and data/labeled/screenshots/blueprint/ with unique
filenames. Collected armor data (with location) is saved to data/collected/armor_<output_folder>.json.

Grid geometry is hardcoded (card origin, step per cell, hover offset, next-page position)
for regular and blueprint modes. The mouse is moved to hover positions so the card
tooltip appears; the card origin (top-left of the armor card) is written to each
screenshot's .txt and used by the task container (verify_card / extract_regions) to
crop and analyze the card.

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

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELED_SCREENSHOTS = REPO_ROOT / "data" / "labeled" / "screenshots"
DATA_COLLECTED = REPO_ROOT / "data" / "collected"

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

# Grid geometry: card origin (1,1), step per cell, hover offset (mouse vs card origin), next-page click
REGULAR_CARD_ORIGIN = (313, 202)
REGULAR_STEP = (174, 179)
REGULAR_HOVER_OFFSET = (-143, 98)
REGULAR_NEXT_PAGE = (666, 1038)
BLUEPRINT_CARD_ORIGIN = (345, 121)
BLUEPRINT_STEP = (126, 129)
BLUEPRINT_HOVER_OFFSET = (-95, 119)
BLUEPRINT_NEXT_PAGE = (555, 990)

LABELED_SUBDIRS = ("labeled/screenshots/regular", "labeled/screenshots/blueprint")
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 300
REQUEST_TIMEOUT_SEC = 120

MOVE_DELAY_S = 0.3
CLICK_DELAY_S = 0.5
FILTER_OPEN_DELAY_S = 0.4
FILTER_AFTER_SELECT_DELAY_S = 0.5
# Temporary: pause after each API result
PAUSE_AFTER_API_RESULT_S = 0.0
# When moving to another cell on the same row, move mouse to (0,0) first for this long
SAME_ROW_RESET_DELAY_S = 0.3


def _ensure_repo_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


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


# Stat key -> display name for card-style logging
_STAT_DISPLAY_NAMES = {
    "base": "Base",
    "fire": "Fire",
    "electric": "Electric",
    "poison": "Poison",
    "hero_hp": "Hero HP",
    "hero_dmg": "Hero Dmg",
    "hero_rate": "Cast Rate",
    "hero_speed": "Speed",
    "offense": "Offense",
    "defense": "Defense",
    "tower_hp": "Tower HP",
    "tower_dmg": "Tower Dmg",
    "tower_rate": "Fire Rate",
    "tower_range": "Range",
}
_ARMOR_STAT_KEYS = ("base", "fire", "electric", "poison")
_HERO_STAT_KEYS = ("hero_hp", "hero_dmg", "hero_rate", "hero_speed", "offense", "defense")
_TOWER_STAT_KEYS = ("tower_hp", "tower_dmg", "tower_rate", "tower_range")


def _format_card_log(result: dict) -> str:
    """Format a verification result as multi-line card-style text for logging.

    Only stats that were detected (key present in results) are shown. If a stat
    was detected but the digit reading failed (value is None or not an int),
    it is shown as NaN.
    """
    armor_set = result.get("armor_set") or "Unknown"
    stats = result.get("stats") or {}
    current = result.get("current_level")
    max_lvl = result.get("max_level")

    def fmt_val(v) -> str:
        return str(v) if isinstance(v, int) else "NaN"

    def row_text(keys: tuple[str, ...]) -> str:
        parts = []
        for k in keys:
            if k not in stats:
                continue
            name = _STAT_DISPLAY_NAMES.get(k, k.replace("_", " ").title())
            parts.append(f"{{{name}: {fmt_val(stats[k])}}}")
        return ", ".join(parts)

    lines = [armor_set]
    for keys in (_ARMOR_STAT_KEYS, _HERO_STAT_KEYS, _TOWER_STAT_KEYS):
        row = row_text(keys)
        if row:
            lines.append(row)
    lines.append(f"Level {fmt_val(current)}/{fmt_val(max_lvl)}")
    return "\n".join(lines)


def is_empty_cell(result: dict) -> bool:
    """True when the cell is an empty armor slot: unknown name and unreadable level."""
    armor_set = result.get("armor_set")
    if armor_set and armor_set not in ("Unknown", ""):
        return False
    return not isinstance(result.get("current_level"), int) and not isinstance(
        result.get("max_level"), int
    )


def is_same_card(a: dict | None, b: dict | None) -> bool:
    """True if two verification results represent the same card. Level can be unreadable."""
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
    """Click the filter button, then the dropdown entry for armor_type."""
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


class _Page:
    """Iterate (row, col) over a page grid. 1-based. start_col/start_row skip leading cells."""

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


def _wait_for_continue_key(stop_requested: list[bool] | None = None) -> bool:
    """Block until the user presses l (returns True) or u (sets stop flag, returns False)."""
    with keyboard.Events() as events:
        for event in events:
            if not isinstance(event, keyboard.Events.Press):
                continue
            c = getattr(event.key, "char", None)
            if c == "l":
                return True
            if c == "u":
                if stop_requested is not None:
                    stop_requested[0] = True
                return False
    return True


def _input_int(prompt: str, default: int | None = None) -> int:
    while True:
        s = input(prompt).strip()
        if default is not None and s == "":
            return default
        try:
            return int(s)
        except ValueError:
            print("Enter an integer.")


def collect_page_counts(armor_types: list[str], blueprint_mode: bool) -> dict[str, int]:
    """Prompt for the page count for each armor type. No auto-filtering.

    The user switches to each armor type in the game manually, then enters the count.
    Any positive integer is accepted; pressing Enter alone defaults to 1.
    """
    mode_label = "blueprint" if blueprint_mode else "regular"
    page_counts: dict[str, int] = {}
    print(f"\nCollecting page counts for {mode_label} mode.")
    print("Switch to each armor type in game, then enter the page count and press Enter.")
    for armor_type in armor_types:
        count = _input_int(f"  [{mode_label}] {armor_type}: how many pages? [1]: ", default=1)
        page_counts[armor_type] = max(1, count)
    return page_counts


def find_first_new_row(
    probe_result: dict,
    prev_page_results: dict[tuple[int, int], dict],
    num_rows: int,
) -> int:
    """Return the first row on the last page that contains new (non-duplicate) armor.

    Compares probe_result (from row=1, col=1 of the last page) against col=1 of each
    row in prev_page_results. If page-N row 1 matches prev-page row R, then rows
    1..(num_rows - R + 1) of page N are duplicates, and the first new row is
    num_rows - R + 2. Returns 1 when no match is found (all rows are new), or
    num_rows + 1 when the entire page is a duplicate (match found at prev-page row 1).
    """
    for r in range(1, num_rows + 1):
        prev_cell = prev_page_results.get((r, 1))
        if prev_cell is not None and is_same_card(probe_result, prev_cell):
            return num_rows - r + 2
    return 1


def _save_collected(collected: list[dict], output_folder: str) -> None:
    """Write the collected armor list to JSON and print a summary."""
    DATA_COLLECTED.mkdir(parents=True, exist_ok=True)
    out_json = DATA_COLLECTED / f"armor_{output_folder}.json"
    with open(out_json, "w") as f:
        json.dump(collected, f, indent=2)
    print(f"Collected {len(collected)} armor pieces -> {out_json.relative_to(REPO_ROOT)}")
    print("Automation finished.")


def run_mode_automation(
    output_folder: str,
    offset: int,
    api_base_url: str,
    blueprint_mode: bool,
    page_counts: dict[str, int],
    global_index_start: int,
    stop_requested: list[bool] | None,
) -> tuple[list[dict], int]:
    """Capture, verify, and save armor screenshots for one mode (regular or blueprint).

    For each armor type:
    - Pages 1..N-1 are fully captured (empty slots skipped).
    - Page N (last page): a single probe screenshot at (row=1, col=1) determines
      which rows are duplicates of page N-1. Only new rows are captured; duplicate
      rows are skipped entirely and the probe file is deleted if not needed.

    Returns (collected_entries, updated_global_index).
    """
    _ensure_repo_path()
    import pyautogui
    from shared.armor_constants import ARMOR_TYPES

    def stopped() -> bool:
        return stop_requested is not None and len(stop_requested) > 0 and stop_requested[0]

    mode_label = "blueprint" if blueprint_mode else "regular"
    subdir = LABELED_SUBDIRS[1] if blueprint_mode else LABELED_SUBDIRS[0]
    out_dir = LABELED_SCREENSHOTS / mode_label
    out_dir.mkdir(parents=True, exist_ok=True)

    if blueprint_mode:
        card_origin_x, card_origin_y = BLUEPRINT_CARD_ORIGIN
        step_x, step_y = BLUEPRINT_STEP
        hoff_x, hoff_y = BLUEPRINT_HOVER_OFFSET
        next_page_pos = BLUEPRINT_NEXT_PAGE
        num_col, num_row = 4, 6
    else:
        card_origin_x, card_origin_y = REGULAR_CARD_ORIGIN
        step_x, step_y = REGULAR_STEP
        hoff_x, hoff_y = REGULAR_HOVER_OFFSET
        next_page_pos = REGULAR_NEXT_PAGE
        num_col, num_row = 5, 3

    first_page_col_start = 1 + (offset % num_col)
    first_page_row_start = 1 + (offset // num_col)

    collected: list[dict] = []
    global_index = global_index_start

    def hover_cell(row: int, col: int) -> tuple[int, int]:
        """Move mouse to the hover position for (row, col). Returns (origin_x, origin_y)."""
        if col > 1:
            pyautogui.moveTo(0, 0)
            time.sleep(SAME_ROW_RESET_DELAY_S)
        origin_x = card_origin_x + (col - 1) * step_x
        origin_y = card_origin_y + (row - 1) * step_y
        pyautogui.moveTo(origin_x + hoff_x, origin_y + hoff_y)
        time.sleep(MOVE_DELAY_S)
        return origin_x, origin_y

    def capture_and_verify(
        row: int, col: int, page_num: int, armor_type: str
    ) -> tuple[dict | None, str, Path, Path]:
        """Hover to cell, capture screenshot, verify. Returns (result | None, base_name, png_path, txt_path).

        None result means a verify failure; an error entry is already appended to collected.
        """
        nonlocal global_index
        origin_x, origin_y = hover_cell(row, col)
        base_name = f"{output_folder}_{armor_type}_p{page_num}_r{row}_c{col}_{global_index:04d}"
        filename = f"{base_name}.png"
        png_path = out_dir / filename
        txt_path = out_dir / f"{base_name}.txt"

        try:
            capture_primary_monitor(png_path)
            txt_path.write_text(f"{origin_x} {origin_y}\n")
        except Exception as e:
            print(f"Error saving {base_name}: {e}", file=sys.stderr)
            global_index += 1
            return None, base_name, png_path, txt_path

        task_id = start_verify(api_base_url, filename, subdir)
        raw = poll_task(api_base_url, task_id)
        results = raw.get("results") or {}
        status = raw.get("status", "")
        global_index += 1

        if status == "failed":
            err = raw.get("error", "Unknown error")
            print(f"Verify failed {base_name}: {err}", file=sys.stderr)
            collected.append({
                "filename": filename,
                "subdir": subdir,
                "armor_type": armor_type,
                "mode": mode_label,
                "page": page_num,
                "row": row,
                "col": col,
                "origin_x": origin_x,
                "origin_y": origin_y,
                "armor_set": None,
                "current_level": None,
                "max_level": None,
                "stats": {},
                "error": err,
            })
            return None, base_name, png_path, txt_path

        result = {
            "armor_set": results.get("armor_set"),
            "current_level": results.get("current_level"),
            "max_level": results.get("max_level"),
            "stats": results.get("stats") or {},
            "error": results.get("error"),
        }
        return result, base_name, png_path, txt_path

    def save_result(
        result: dict,
        base_name: str,
        png_path: Path,
        armor_type: str,
        page_num: int,
        row: int,
        col: int,
    ) -> None:
        """Append a verified cell to collected and print a log line."""
        origin_x = card_origin_x + (col - 1) * step_x
        origin_y = card_origin_y + (row - 1) * step_y
        collected.append({
            "filename": png_path.name,
            "subdir": subdir,
            "armor_type": armor_type,
            "mode": mode_label,
            "page": page_num,
            "row": row,
            "col": col,
            "origin_x": origin_x,
            "origin_y": origin_y,
            "armor_set": result.get("armor_set"),
            "current_level": result.get("current_level"),
            "max_level": result.get("max_level"),
            "stats": result.get("stats"),
            "error": result.get("error"),
        })
        print(f"Saved {base_name}:")
        print(_format_card_log(result))
        print()
        time.sleep(PAUSE_AFTER_API_RESULT_S)

    def delete_files(*paths: Path) -> None:
        for p in paths:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    for armor_type in ARMOR_TYPES:
        if stopped():
            break
        select_armor_filter(pyautogui, blueprint_mode, armor_type)
        num_pages = page_counts.get(armor_type, 1)
        prev_page_results: dict[tuple[int, int], dict] = {}

        for page_num in range(1, num_pages + 1):
            if stopped():
                break
            is_last_page = page_num == num_pages

            if is_last_page and num_pages > 1:
                # Probe (row=1, col=1) to find where duplicate rows end on this last page.
                probe_result, probe_base, probe_png, probe_txt = capture_and_verify(
                    row=1, col=1, page_num=page_num, armor_type=armor_type,
                )
                if probe_result is None:
                    continue  # verify error on probe; already logged

                first_new_row = find_first_new_row(probe_result, prev_page_results, num_row)

                if first_new_row > num_row:
                    # Every row on this page is a duplicate of the previous page.
                    print(
                        f"[{mode_label}] {armor_type} page {page_num}: "
                        "all rows duplicated, skipping."
                    )
                    delete_files(probe_png, probe_txt)

                elif first_new_row > 1:
                    # Probe is in a duplicate row; discard it and capture unique rows only.
                    delete_files(probe_png, probe_txt)
                    for row, col in _Page(num_col, num_row, start_row=first_new_row):
                        if stopped():
                            break
                        result, base_name, png_path, txt_path = capture_and_verify(
                            row=row, col=col, page_num=page_num, armor_type=armor_type,
                        )
                        if result is None:
                            continue
                        if is_empty_cell(result):
                            delete_files(png_path, txt_path)
                            continue
                        save_result(result, base_name, png_path, armor_type, page_num, row, col)

                else:
                    # Probe is in a new row (first_new_row == 1); save it then capture the rest.
                    if is_empty_cell(probe_result):
                        delete_files(probe_png, probe_txt)
                    else:
                        save_result(probe_result, probe_base, probe_png, armor_type, page_num, 1, 1)
                    for row, col in _Page(num_col, num_row, start_col=2, start_row=1):
                        if stopped():
                            break
                        result, base_name, png_path, txt_path = capture_and_verify(
                            row=row, col=col, page_num=page_num, armor_type=armor_type,
                        )
                        if result is None:
                            continue
                        if is_empty_cell(result):
                            delete_files(png_path, txt_path)
                            continue
                        save_result(result, base_name, png_path, armor_type, page_num, row, col)

            else:
                # Non-last page, or a single-page type: full capture with optional offset.
                if page_num == 1 and offset > 0:
                    page_iter = _Page(num_col, num_row, first_page_col_start, first_page_row_start)
                else:
                    page_iter = _Page(num_col, num_row)

                current_page_results: dict[tuple[int, int], dict] = {}
                rows_with_content: set[int] = set()

                for row, col in page_iter:
                    if stopped():
                        break
                    result, base_name, png_path, txt_path = capture_and_verify(
                        row=row, col=col, page_num=page_num, armor_type=armor_type,
                    )
                    if result is None:
                        continue
                    if is_empty_cell(result):
                        delete_files(png_path, txt_path)
                        if (
                            num_pages == 1
                            and col == num_col
                            and row not in rows_with_content
                        ):
                            break
                        continue
                    save_result(result, base_name, png_path, armor_type, page_num, row, col)
                    current_page_results[(row, col)] = result
                    rows_with_content.add(row)

                prev_page_results = current_page_results

            if not is_last_page:
                px, py = next_page_pos
                pyautogui.moveTo(px, py)
                time.sleep(MOVE_DELAY_S)
                pyautogui.click()
                time.sleep(CLICK_DELAY_S)

    return collected, global_index


def main() -> None:
    _ensure_repo_path()
    from shared.armor_constants import ARMOR_TYPES

    if urllib is None:
        print("urllib required for API calls.", file=sys.stderr)
        sys.exit(1)

    offset = _input_int("Offset (non-armor cells on first page, 0 or more) [0]: ", 0)
    if offset < 0:
        offset = 0
    output_folder = input(
        "Output folder name (used for filenames and data/collected/armor_<name>.json) [armor_run]: "
    ).strip()
    if not output_folder:
        output_folder = "armor_run"
    api_base_url = get_api_base_url()

    print()
    print("Keys: l = continue / start, u = quit (global; works even when game has focus).")
    print(f"Armor types: {', '.join(ARMOR_TYPES)}")
    print(f"API: {api_base_url}")

    stop_requested: list[bool] = [False]

    def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
        c = getattr(key, "char", None)
        if c == "u":
            stop_requested[0] = True

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

    DATA_COLLECTED.mkdir(parents=True, exist_ok=True)
    collected: list[dict] = []
    global_index = 0

    # --- Regular mode ---
    print()
    print("Navigate to regular armor mode in game, then press l to collect page counts (u to quit).")
    if not _wait_for_continue_key(stop_requested):
        print("Quit.")
        return

    regular_page_counts = collect_page_counts(ARMOR_TYPES, blueprint_mode=False)
    print()
    print("Regular page counts:")
    for t, c in regular_page_counts.items():
        print(f"  {t}: {c} page(s)")
    print()
    print("Press l to begin regular automation (u to quit).")
    if not _wait_for_continue_key(stop_requested):
        print("Quit.")
        return

    stop_requested[0] = False
    regular_collected, global_index = run_mode_automation(
        output_folder, offset, api_base_url,
        blueprint_mode=False,
        page_counts=regular_page_counts,
        global_index_start=global_index,
        stop_requested=stop_requested,
    )
    collected.extend(regular_collected)

    if stop_requested[0]:
        print("Stopped by u key.")
        _save_collected(collected, output_folder)
        return

    # --- Blueprint mode ---
    print()
    print(
        f"Regular mode done ({len(regular_collected)} pieces). "
        "Switch to blueprint mode in game, then press l to collect page counts (u to quit)."
    )
    if not _wait_for_continue_key(stop_requested):
        print("Quit.")
        _save_collected(collected, output_folder)
        return

    blueprint_page_counts = collect_page_counts(ARMOR_TYPES, blueprint_mode=True)
    print()
    print("Blueprint page counts:")
    for t, c in blueprint_page_counts.items():
        print(f"  {t}: {c} page(s)")
    print()
    print("Press l to begin blueprint automation (u to quit).")
    if not _wait_for_continue_key(stop_requested):
        print("Quit.")
        _save_collected(collected, output_folder)
        return

    stop_requested[0] = False
    blueprint_collected, global_index = run_mode_automation(
        output_folder, offset, api_base_url,
        blueprint_mode=True,
        page_counts=blueprint_page_counts,
        global_index_start=global_index,
        stop_requested=stop_requested,
    )
    collected.extend(blueprint_collected)

    if stop_requested[0]:
        print("Stopped by u key.")

    _save_collected(collected, output_folder)


if __name__ == "__main__":
    main()
