# Screenshot augmentation for box-detector training

Augmentation is performed **inside the training process**, not by a standalone script. When you start a box-detector training task, the worker loads labeled screenshots from `data/labeled/screenshots/regular/` and `data/labeled/screenshots/blueprint/`, and for each training epoch it generates augmented samples in memory.

## Pipeline: crop then label-aware augmentation

1. **Crop**: Config (`extract.augment.regular` and `extract.augment.blueprint` in config.yaml) defines **crop margins only** (x_neg, x_pos, y_neg, y_pos): the maximum fraction of the full image discarded per side. These margins are **cropped out** entirely—the inner rectangle is the content image. Labels (origin_x, origin_y) are on the **uncropped** image; they are transformed to cropped coordinates for training.
2. **Label-aware augmentation**: On the cropped image, random translation (shift + black or noise fill) is applied. **Translation limits are geometric only** (label + box size in cropped space), not capped by config. We allow as much shift as keeps the full detection box in frame, so the box can be pushed to the crop edges in all four directions. See [shared/box_detector_augment.py](../shared/box_detector_augment.py) (`crop_to_inner_rect`, `augment_sample_label_aware`).

## Data flow

- **Input**: `data/labeled/screenshots/<type>/` with `.png` and `.txt` (one line: `origin_x origin_y`) per image. Use the Extract config UI to set the origin and click **Save origin** for each screenshot.
- **At training time**: The training processor crops each image with the config bounds, then uses label-aware augmentation to produce (image, origin) pairs on the fly. No separate augmented output directories are required.

## Configuration

Crop margins (x_neg, x_pos, y_neg, y_pos) and augment options are read from **config.yaml** under `extract.augment` (and by the task worker for training). The API and worker use the same config. Key points:

- **Crop margins** (regular/blueprint): Define how much of the full image is discarded per side; they do **not** cap augmentation translation (translation is geometric only).
- **augment.fill**: `black` or `noise` for the area revealed by shift.
- **augment.count**: Number of augmented images generated per source image per epoch.

## Layout reference

Paths and the `.txt` format are defined in [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md).
