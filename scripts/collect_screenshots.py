"""Capture screenshots of the primary monitor on key sequence o then p. Press u to quit.

Run from repo root: python3 scripts/collect_screenshots.py

- i: toggle between regular (armor) and blueprint mode; screenshots save to
  data/labeled/screenshots/regular/ or data/labeled/screenshots/blueprint/ per shared/DATA_LAYOUT.md.
"""

import sys
from pathlib import Path

from pynput import keyboard

# Repo root (relative to repo root per DATA_LAYOUT.md)
REPO_ROOT = Path(__file__).resolve().parent.parent
LABELED_SCREENSHOTS = REPO_ROOT / "data" / "labeled" / "screenshots"


def screenshots_dir(blueprint_mode: bool) -> Path:
    """Return the directory for the current mode (regular or blueprint)."""
    subdir = "blueprint" if blueprint_mode else "regular"
    return LABELED_SCREENSHOTS / subdir


def next_screenshot_path(blueprint_mode: bool) -> Path:
    """Return the next sequential screenshot path for the current mode."""
    out_dir = screenshots_dir(blueprint_mode)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = list(out_dir.glob("*.png"))
    indices = []
    for p in existing:
        stem = p.stem
        if stem.isdigit():
            indices.append(int(stem))
    next_index = max(indices, default=0) + 1
    return out_dir / f"{next_index:03d}.png"


def capture_primary_monitor(save_path: Path) -> None:
    """Capture the primary monitor (mss index 1) and save as PNG to save_path."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        # monitors[0] = all monitors; monitors[1] = first physical (typically primary)
        mon = sct.monitors[1]
        shot = sct.grab(mon)
        # mss returns BGRA; Pillow BGRX decoder gives us RGB
        img = Image.frombytes(
            "RGB",
            (shot.width, shot.height),
            shot.bgra,
            "raw",
            "BGRX",
        )
        img.save(save_path)


def main() -> None:
    blueprint_mode = False

    def mode_label() -> str:
        return "blueprint" if blueprint_mode else "regular"

    print("Screenshot collection: o then p to capture, i to toggle regular/blueprint, u to quit.")
    print(f"Mode: {mode_label()} -> {screenshots_dir(blueprint_mode).relative_to(REPO_ROOT)}")
    print()

    with keyboard.Events() as events:
        for event in events:
            if not isinstance(event, keyboard.Events.Press):
                continue
            key = event.key
            c = getattr(key, "char", None)

            if c == "u":
                print("Quit (u).")
                return

            if c == "i":
                blueprint_mode = not blueprint_mode
                print(f"Mode: {mode_label()} -> {screenshots_dir(blueprint_mode).relative_to(REPO_ROOT)}")
                continue

            if c != "o":
                continue

            # Got 'o'; wait for 'p' or 'u' or 'i'
            next_ev = next(events)
            if not isinstance(next_ev, keyboard.Events.Press):
                continue
            next_key = next_ev.key
            c = getattr(next_key, "char", None)
            if c == "u":
                print("Quit (u).")
                return
            if c == "i":
                blueprint_mode = not blueprint_mode
                print(f"Mode: {mode_label()} -> {screenshots_dir(blueprint_mode).relative_to(REPO_ROOT)}")
                continue
            if c != "p":
                continue

            # o then p: capture
            out_path = next_screenshot_path(blueprint_mode)
            try:
                capture_primary_monitor(out_path)
                rel = out_path.relative_to(REPO_ROOT)
                print(f"Took screenshot [{mode_label()}]: {rel}")
            except Exception as e:
                print(f"Error capturing screenshot: {e}", file=sys.stderr)
                raise


if __name__ == "__main__":
    main()
