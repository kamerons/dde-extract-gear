# Screenshot augmentation for box-detector training

Augmentation is performed **inside the training process**, not by a standalone script. When you start a box-detector training task, the worker loads labeled screenshots from `data/labeled/screenshots/regular/` and `data/labeled/screenshots/blueprint/`, and for each training epoch it generates augmented samples in memory: random shift + black or noise fill, with origins updated so labels stay correct.

## Data flow

- **Input**: `data/labeled/screenshots/<type>/` with `.png` and `.txt` (one line: `origin_x origin_y`) per image. Use the Extract config UI to set the origin and click **Save origin** for each screenshot.
- **At training time**: The training processor uses [shared/box_detector_augment.py](../shared/box_detector_augment.py) to produce augmented (image, origin) pairs on the fly for the training set. No separate augmented output directories are required.

## Environment variables

These are read by the API and by the task worker for augmentation during training (and for the augmentation preview in the Extract config UI):

| Variable | Description | Default |
|----------|-------------|---------|
| `EXTRACT_AUGMENT_SHIFT_REGULAR` | Max shift as a fraction of the smaller image dimension (0–1) for regular screenshots | `0.1` |
| `EXTRACT_AUGMENT_SHIFT_BLUEPRINT` | Same, for blueprint screenshots | `0.1` |
| `EXTRACT_AUGMENT_FILL` | Fill for the shifted area: `black` or `noise` | `black` |
| `EXTRACT_AUGMENT_COUNT` | Number of augmented images generated per source image per epoch | `3` |

## Layout reference

Paths and the `.txt` format are defined in [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md).
