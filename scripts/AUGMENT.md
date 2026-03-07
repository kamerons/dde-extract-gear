# Screenshot augmentation for box-detector training

The augmentation script produces shifted copies of labeled screenshots so the box detector can be trained with small translations. Each output image has the same dimensions as the input; the image is pasted at a random offset and the remainder is filled with black or noise. The companion `.txt` origin is updated so labels stay correct.

## Data flow

- **Input**: `data/labeled/screenshots/regular/` and `data/labeled/screenshots/blueprint/`. Each image must have a companion `.txt` with one line: `origin_x origin_y` (the box top-left). Use the Extract config UI to set the origin and click **Save origin** for each screenshot.
- **Output**: `data/labeled/augmented/regular/` and `data/labeled/augmented/blueprint/`. Files are named `<id>_<n>.png` and `<id>_<n>.txt` (e.g. `001_1.png`, `001_1.txt`) for the Nth augmented copy of source `<id>.png`.

## Environment variables

Set these (e.g. in `.env` or the shell) before running the script:

| Variable | Description | Default |
|----------|-------------|---------|
| `EXTRACT_AUGMENT_SHIFT_REGULAR` | Max shift as a fraction of the smaller image dimension (0–1) for regular screenshots | `0.1` |
| `EXTRACT_AUGMENT_SHIFT_BLUEPRINT` | Same, for blueprint screenshots | `0.1` |
| `EXTRACT_AUGMENT_FILL` | Fill for the shifted area: `black` or `noise` | `black` |
| `EXTRACT_AUGMENT_COUNT` | Number of augmented images to generate per source image | `3` |

The same variables are used by the API/frontend for the augmentation preview in the Extract config UI.

## Running the script

From the repo root with the virtualenv activated:

```bash
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements-scripts.txt
python3 scripts/augment_screenshots.py
```

Images without a `.txt` file are skipped (a message is printed to stderr). The script creates the output directories if they do not exist.

## Layout reference

Paths and the `.txt` format are defined in [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md).
