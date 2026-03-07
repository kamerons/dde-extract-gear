# Screenshot collection script (plan)

## Goal

A Python script that captures screenshots of the game for later labeling and training. The user positions the game (e.g. hovers over a gear slot) and triggers a capture; the script saves the image under the data directory.

## Behavior

- **Trigger**: Listen for a key combination, e.g. **o** then **p** (same idea as the legacy collect flow). On that sequence, take a single screenshot.
- **Output**: Save each screenshot under the data directory, e.g. `data/unlabeled/screenshots/`, with sequential naming such as `001.png`, `002.png`, etc.
- **Scope**: Capture on user trigger only; no automatic or periodic capture unless explicitly specified later.

## Alignment with data layout

Output paths and naming must follow the canonical layout in [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md) so that downstream steps (labeling, box detector training) can assume a consistent structure.

## Dependencies

Specific libraries (e.g. for keyboard listening and screen capture) are TBD; the legacy code used `api_pyautogui` and `api_keyboard`-style abstractions for reference.
