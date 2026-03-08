# Crop, label-aware augmentation, test split, and training preview – summary

This document summarizes the changes made to how images are cropped and augmented for box-detector training, how the test set is split, and how augmented samples appear in the training preview.

---

## 1. Crop (config bounds remove margins)

**Before:** The config values `extract.augment.regular` and `extract.augment.blueprint` (x_neg, x_pos, y_neg, y_pos) were used only as **shift bounds** for augmentation (random translation with fill).

**After:** Those values define the **crop region only** (crop margins: max fraction of full image discarded per side). The margins are cropped out; only the inner rectangle is kept. They are **not** used to cap augmentation translation (translation uses geometric limits; see §2).

- **Shared helper** ([shared/box_detector_augment.py](shared/box_detector_augment.py)): `crop_to_inner_rect(img, x_neg, x_pos, y_neg, y_pos)` returns `(cropped_img, crop_left, crop_top)` so callers can convert uncropped labels to cropped coordinates: `origin_crop_x = origin_x - crop_left`, `origin_crop_y = origin_y - crop_top`.
- **Training and evaluation** use the cropped image and cropped-space origins for all downstream steps (augmentation and model input).
- Cropped size is clamped so it is always at least 1 pixel per axis.

---

## 2. Label-aware augmentation

**Before:** Random translation (dx, dy) was sampled uniformly within config-based pixel bounds, so the labeled box could end up shifted out of frame.

**After:** Translation is limited **only by geometry** (no config cap). We allow as much shift as keeps the **full detection box** (card + set + stat + level regions) inside the cropped image, so the box can be pushed to the crop edges in all four directions.

- **Shared helper** ([shared/box_detector_augment.py](shared/box_detector_augment.py)): `augment_sample_label_aware(..., scale, image_type)` uses `compute_detection_extents(scale, image_type)` from [shared/extract_regions.py](shared/extract_regions.py) to get how far the full box extends left, top, right, and bottom from the origin. Translation limits are **geometric only** (e.g. `max_dx_neg = origin_crop_x - left_extent` so the left edge of the box can reach the left crop edge); the entire box remains in `[0, cw) × [0, ch)`.
- Labels are defined on the **uncropped** image; after the crop step we work in cropped space, so augmentation uses the origin in cropped coordinates.
- If the origin falls outside the crop rect (e.g. mislabeled), it is clamped to the cropped image bounds before computing shift limits.
- **Translation margin lines:** When "Show cropped area" is checked, the frontend requests boxes with image dimensions; the API returns `translation_margin_lines` (four segments in cropped pixels: left, top, right, bottom). Each segment runs from the detection box edge to the crop edge and shows the **geometric** limit (maximum translation in that direction without cutting off the box). Translation is allowed up to that full range; it is not capped by config. The frontend draws these as thick orange lines with an arrow-head at the crop edge so it is clear the line does not extend past the image.

---

## 3. Stratified test set (50% blueprint)

**Before:** Train/test split was a single sort by (type, name) with the last `test_ratio` fraction as test, so the test set could be mostly regular or mostly blueprint depending on the data.

**After:** The test set is **stratified** so that (by default) **50% of test images are blueprints** and 50% are regular.

- **Config:** `box_detector.test_blueprint_fraction` (default `0.5`) in [config.yaml](config.yaml) / [config.yaml.example](config.yaml.example) and [task/config.py](task/config.py).
- **Split logic** ([task/processors/box_detector_processor.py](task/processors/box_detector_processor.py)): `_split_train_test(sources, test_ratio, test_blueprint_fraction)` splits regular and blueprint sources separately and takes test from each so the combined test set has the desired blueprint fraction. If one type has too few samples, the rest of the test set is filled from the other type.
- Training, evaluation, and preview all use this stratified split.

---

## 4. Training preview includes augmented samples

**Before:** The training preview (Next/Previous list) showed one item per **test source** image (cropped), with GT and predicted boxes.

**After:** The preview shows one item per **augmented test sample** (test_sources × augment_count). Each item is the exact image the model was run on, with embedded image and GT/pred in that image's space.

- **Preview build** ([task/processors/evaluation_processor.py](task/processors/evaluation_processor.py)): `build_preview_items` now:
  - For each test source: crop, then generate `augment_count` augmented samples (same pipeline as training).
  - Runs the model on the full augmented test set.
  - Returns one item per augmented sample, each with:
    - `image_data_url`: base64 PNG of that augmented image (so no separate image fetch).
    - `origin_x`, `origin_y`, `pred_x`, `pred_y`: in the augmented image's coordinate space.
    - `filename`, `subdir`, `augment_index` (1-based) for display.
- **Frontend** ([frontend/src/components/TrainingPreview.tsx](frontend/src/components/TrainingPreview.tsx)): Uses `item.image_data_url` as the image `src` when present; otherwise falls back to `getScreenshotUrl(..., { crop: true })`. The index line shows e.g. `3 / 24 (001.png · augment 2)` when `augment_index` is set.

So you can step through **every** augmented test image in the existing Next/Previous UI and see how the model did on each.

---

## 5. Removed separate "Sample augments" UI

The earlier design had a separate "Sample augments" section (dropdown to pick a source image, count, "Show augments" button, grid of cropped base + augments) and a **GET /api/extract/training/augment-preview** endpoint. That was removed so that:

- Augments only appear in the **training preview** list (Next/Previous) as part of the normal training-result API.
- There is no second UI or endpoint for viewing augments.

---

## 6. Screenshot endpoint: optional crop

For compatibility and for any non-augment preview use, the screenshot endpoint supports a **crop** query parameter:

- **GET /api/extract/screenshots/{filename}?subdir=...&crop=1**  
  When `crop=1` and `subdir` is `labeled/screenshots/regular` or `labeled/screenshots/blueprint`, the response is the **cropped** image (same bounds as training).  
  The frontend uses this when an item does not have `image_data_url` (e.g. older cached previews).

---

## 7. Files touched (overview)

| Area | Files |
|------|--------|
| Crop + augment helpers | [shared/box_detector_augment.py](shared/box_detector_augment.py): `crop_to_inner_rect`, `augment_sample_label_aware`, `compute_translation_margin_lines` |
| Training pipeline | [task/processors/box_detector_processor.py](task/processors/box_detector_processor.py): `_build_arrays` (crop then label-aware augment), `_split_train_test` (stratified), `test_blueprint_fraction` |
| Eval / preview | [task/processors/evaluation_processor.py](task/processors/evaluation_processor.py): `build_preview_items` (augmented items + `image_data_url`), stratified split, crop in preview |
| Worker | [task/worker.py](task/worker.py): pass `test_blueprint_fraction` to processor and eval/preview |
| API | [api/routes/extract.py](api/routes/extract.py): `serve_screenshot` with `crop`; POST `/api/extract/boxes` accepts optional `image_width`/`image_height` and returns `translation_margin_lines`; removed augment-preview endpoint and translation_safe_origin_rect from config |
| Frontend | [frontend/src/components/TrainingPreview.tsx](frontend/src/components/TrainingPreview.tsx): use `image_data_url`, show augment index; [frontend/src/components/ExtractTraining.tsx](frontend/src/components/ExtractTraining.tsx): removed Sample augments UI; [frontend/src/components/OriginScaleEditor.tsx](frontend/src/components/OriginScaleEditor.tsx): "Show cropped area" draws translation margin lines (orange, arrow at crop edge); [frontend/src/api/extract.ts](frontend/src/api/extract.ts): `getScreenshotUrl` crop option, `fetchBoxes` with optional image size, `TranslationMarginLines`, `TrainingPreviewItem` fields |
| Config | [config.yaml](config.yaml), [config.yaml.example](config.yaml.example), [task/config.py](task/config.py): `test_blueprint_fraction` |
| Docs | [scripts/AUGMENT.md](scripts/AUGMENT.md), [docs/EXTRACT_TRAINING_FLOW.md](docs/EXTRACT_TRAINING_FLOW.md): crop-first pipeline, label-aware augmentation, stratified split, preview with augments |

---

## 8. Data flow (high level)

1. **Load** full image and origin (uncropped) from disk.
2. **Crop** using config bounds → cropped image and `(origin_crop_x, origin_crop_y)`.
3. **Augment** (training/preview): label-aware random shift + fill on cropped image → `augment_count` samples per source; each has `(aug_img, new_ox, new_oy)`.
4. **Model**: resize to 256×256, predict; scale predictions back to image space for metrics and preview items.
5. **Preview**: one item per augmented sample, with `image_data_url` and GT/pred so the Next/Previous list shows every augment and how the model performed on it.
