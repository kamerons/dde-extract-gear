# Translation margin visualization and augmentation fixes – summary

This document summarizes the work done to address data augmentation shifting images too far (cutting off content the network needs) and to improve how translation limits are visualized and debugged.

---

## 1. Translation margin lines (replacing the safe-origin box)

**Problem:** The UI showed a "translation safe origin rect" (dashed green box) that was hard to interpret. The idea was to show how much the image could shift without losing the detection box.

**Change:** Replaced that rect with **four thick orange lines** from the detection box edges to the cropped image edges, with an arrow-head at the image edge, so it’s clear where the limit is.

- **Backend** ([shared/box_detector_augment.py](shared/box_detector_augment.py)): Added `compute_translation_margin_lines()` which, given origin, image size, crop bounds, scale, and image type, returns four segments in cropped pixel space (left, top, right, bottom), each from box edge to crop edge, using box center for the perpendicular coordinate.
- **API** ([api/routes/extract.py](api/routes/extract.py)): `POST /api/extract/boxes` accepts optional `image_width` and `image_height`; when present, the response includes `translation_margin_lines`. Removed `translation_safe_origin_rect_*` from `GET /api/extract/config`.
- **Frontend** ([frontend/src/components/OriginScaleEditor.tsx](frontend/src/components/OriginScaleEditor.tsx), [frontend/src/api/extract.ts](frontend/src/api/extract.ts)): When "Show cropped area" is checked, the UI requests boxes with image dimensions and draws the four orange lines (and arrows) from the box to the crop edges. Removed all use of the old safe-origin rect types and config fields.
- **Docs:** [docs/CROP_AUGMENT_AND_PREVIEW_SUMMARY.md](docs/CROP_AUGMENT_AND_PREVIEW_SUMMARY.md) updated to describe the new margin-line visualization.

---

## 2. Label-aware augmentation: use actual content position

**Problem:** In the training preview, the **correct (GT) box** sometimes appeared offscreen—the image looked cropped or translated too much relative to where the box was drawn.

**Cause:** In `augment_sample_label_aware()` the origin was clamped to the crop for computing shift limits, and the returned "new origin" was the clamped origin plus shift. The **actual** content in the cropped image stays at the saved label `(origin_crop_x, origin_crop_y)`. So we were (a) allowing shifts that kept a *clamped* box in frame instead of the real content, and (b) returning an origin that didn’t match where the card actually was in the augmented image.

**Change** ([shared/box_detector_augment.py](shared/box_detector_augment.py)):

- Config **x_neg, x_pos, y_neg, y_pos** define **crop only** (max fraction of full image discarded per side). They are not used to cap augmentation translation.
- **Translation limits are geometric only**: actual label (origin in cropped space) plus box extents from `compute_detection_extents`. The box can be pushed to the crop edges in all four directions; no config cap on shift.
- **Shift limits** are computed from the **unclamped** `origin_crop_x`, `origin_crop_y`, so the allowed translation keeps the detection box at the *actual* content position inside the crop.
- **Returned origin** is now `(origin_crop_x + dx, origin_crop_y + dy)` instead of `(ox + dx, oy + dy)`, so the preview’s GT boxes are drawn at the real content position in the augmented image.

This keeps the green box aligned with the card and avoids the "correct box offscreen" effect when the saved origin was near or past the crop edge.

---

## 3. Diagonal max-shift preview script

**Purpose:** To inspect, in isolation, how far the image is *allowed* to shift in each diagonal direction and whether the detection box stays fully in frame.

**Added:** [scripts/show_max_augment_diagonals.py](scripts/show_max_augment_diagonals.py)

- Loads a labeled screenshot and its `.txt` origin, uses the same crop and label-aware limit math as training.
- Builds four images with shifts at the four diagonal extremes: (-dx,-dy), (+dx,-dy), (+dx,+dy), (-dx,+dy) using the computed `max_dx_neg`, `max_dx_pos`, `max_dy_neg`, `max_dy_pos`.
- Saves a 2×2 grid to `scripts/max_augment_diagonals.png` and opens it in the system default viewer.
- Run from repo root:  
  `python scripts/show_max_augment_diagonals.py [image.png] [regular|blueprint]`  
  If no image is given, uses the first labeled image in `data/labeled/screenshots/regular`.

**Dependency:** `matplotlib>=3.7.0` was added to [requirements.txt](requirements.txt) for generating the figure.

---

## 4. Fix: geometric-only translation limits

The large discrepancy (e.g. ~30% of box height on top/bottom, ~30px gap in -x) was caused by **config being (incorrectly) used as shift caps**: the same x_neg/x_pos/y_neg/y_pos fractions were applied to cap how far the image could translate, so allowed shift was much smaller than the geometric room. The fix is:

- **Translation limits are geometric only** (label + box extents in cropped space). Config defines crop only; we allow as much shift as keeps the full box in frame, so the box can reach the crop edges in all four directions.
- **Off-by-one fix** for the positive x and y bounds: use `cw - origin_crop_x - right_ext` and `ch - origin_crop_y - bottom_ext` (not `cw - 1` / `ch - 1`) so the box can sit flush with the right and bottom crop edges.
