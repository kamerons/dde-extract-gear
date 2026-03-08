# Extract Training & Preview Flow

This document describes how box-detector training, model saving, and the training preview work end-to-end.

---

## 1. Configuration

- **Env:** `BOX_DETECTOR_MODEL_PATH` (default `data/box_detector_model`), `DATA_DIR` (default `data`), `BOX_DETECTOR_TEST_RATIO`, `TRAINING_EPOCHS`, etc.
- **API** uses `api.config.Config`; **worker** uses `task.config.Config`. Both read the same env vars.
- **Repo root** is resolved as:
  - API: `Path(__file__).resolve().parent.parent.parent` -> from `api/routes/extract.py` -> repo root.
  - Worker: `Path(__file__).resolve().parent.parent` -> from `task/worker.py` -> repo root.
- In Docker, repo root is typically `/app`; `data` is usually mounted as `../data:/app/data`.

---

## 2. Training Start (API -> Redis -> Worker)

1. **Frontend** calls `POST /api/extract/training/start` (optional body: `{ "model_type": "box_detector" }`).
2. **API** (`api/routes/extract.py` -> `training_start`) uses `TaskService.create_training_task(model_type)`.
3. **TaskService** (`api/services/task_service.py`):
   - Generates a new `task_id` (UUID).
   - If a training task is already running (`TRAINING_CURRENT_TASK_KEY`), sets `task:{current_id}:cancelled` to `"1"` so the worker will stop it.
   - Clears the `training_tasks` Redis list and pushes a single payload: `{ "task_id": "...", "model_type": "box_detector" }`.
   - Writes task metadata to `task:{task_id}:meta` (status `pending`, task_type `training`, etc.) with TTL.
4. **API** returns `{ "task_id": "...", "status": "pending" }`.
5. **Frontend** stores `task_id` and polls `GET /api/tasks/{task_id}` every 2s.

6. **Worker** (`task/worker.py`) has one **long-running slot thread** that uses `brpop([TRAINING_QUEUE_NAME, QUEUE_NAME], timeout=...)` (so at most one training or one recommendation runs at a time) and an **evaluation worker pool** that consumes from `evaluation_tasks`. When the long-running slot pops a training task from `training_tasks`:
   - Parses `task_data` -> `task_id`, `model_type`.
   - Sets `TRAINING_CURRENT_TASK_KEY` to `task_id` (so API knows who is running).
   - Updates `task:{task_id}:meta` to `status: "processing"`.
   - Starts a **background eval thread** (see below), then calls `self.training_processor.process(...)`.

---

## 3. Training Run (Processor)

**BoxDetectorProcessor** (`task/processors/box_detector_processor.py`):

1. **Paths:**
   - `_data_dir_abs` = `_repo / config.DATA_DIR` (e.g. `/app/data`). Model files are written under a subdir so they always land on the mounted volume.
   - `save_dir` = `_data_dir_abs / "models" / "box_detector"` (e.g. `data/models/box_detector/`); `stem` = `Path(model_path).name` (e.g. `box_detector_model`).
   - Checkpoint: `save_dir / (stem + "_current.keras")`.
   - Final: `save_dir / (stem + "_YYYYMMDD_HHMMSS.keras")` and `save_dir / (stem + ".keras")`.

2. **Data:**
   - Scans `data/labeled/screenshots/regular` and `data/labeled/screenshots/blueprint` for `*.png` with a matching `.txt` (origin x,y).
   - **Train/test split:** Stratified so the test set is ~50% blueprint (configurable via `box_detector.test_blueprint_fraction`). Regular and blueprint are split separately; test takes the last N of each to achieve the target ratio.
   - **Each epoch:** re-scans labeled dirs and re-splits (same stratified logic). As you label new images, both train and test sets grow.

3. **Per epoch:**
   - Get current sources, split into train/test (stratified).
   - **Crop:** Each image is cropped using config margins (`extract.augment.regular` / `blueprint`); labels are transformed to cropped coords.
   - **Augment:** Label-aware random shift + fill on the cropped image. Translation uses **geometric limits only** (label + box in cropped space), not config—the box can be pushed to the crop edges.
   - Build train arrays (augmented) and test arrays (augmented) for validation and metrics.
   - Run `model.fit(..., validation_data=(X_test_aug, y_test_aug))`.
   - Call `progress_callback(epoch, total_epochs, metrics)` -> worker writes to Redis.
   - Save **checkpoint** to `save_dir / (stem + "_current.keras")` (with logging; warns if file missing after save).
   - Check `check_cancelled()`; if set, raise `TaskCancelledError`.

4. **After last epoch:**
   - Re-split current sources for final test set; build augmented test arrays.
   - Save **final model** to `save_dir`: timestamped `stem_YYYYMMDD_HHMMSS.keras` and legacy `stem.keras`. Logs paths and errors if files are missing after save.
   - Return `final_metrics` to the worker.

5. **Worker** then:
   - Clears `TRAINING_CURRENT_TASK_KEY`.
   - Calls `update_task_status(task_id, "completed", results=results)` (writes to `task:{task_id}:meta` and `task:{task_id}:result`).
   - Stops the eval thread (sets stop event, joins).

---

## 4. Worker Eval Loop (Background Thread)

- **Started** when a box_detector training task begins; **stopped** when the task finishes (success, fail, or cancel).
- **Role:** Every 10s, load the **current checkpoint** and write test metrics to Redis so the UI can show live metrics without calling the API's evaluate endpoint.

**Steps:**

1. `data_dir` = `repo_root / config.DATA_DIR`; `stem` = `Path(BOX_DETECTOR_MODEL_PATH).name`; `current_path` = `data_dir / (stem + "_current.keras")` (same layout as processor).
2. If `current_path` does not exist, skip (no checkpoint yet).
3. Load model with the shared loader (format detection and logging: `.keras` zip vs HDF5); see `task/processors/evaluation_processor._load_box_detector_model`.
4. Recompute test set: `_labeled_dirs`, `_scan_sources`, `_split_train_test` (stratified, 50% blueprint), then `_build_arrays` (crop + augment=True) for a larger test set.
5. Compute metrics with `_compute_test_metrics(model, X_test, y_test)`.
6. Write to Redis: `task:{task_id}:eval` = JSON of metrics, TTL 3600s. Also build preview items (same model and test set, augment=False) and write to `task:{task_id}:latest_preview` and `extract:training:latest_preview` (items, scale_regular, scale_blueprint).

---

## 5. API: How the Model Path Is Chosen

**`_box_detector_load_path()`** in `api/routes/extract.py`:

- **Directory:** `model_dir = _data_dir() / "models" / "box_detector"` (same as processor's save dir). **Stem:** `Path(config.BOX_DETECTOR_MODEL_PATH).name` (e.g. `box_detector_model`).
- **Order of resolution:**
  1. **Current checkpoint:** If `model_dir / (stem + "_current.keras")` exists -> return it. (Used while training is in progress.)
  2. **Latest timestamped:** In `model_dir`, glob `{stem}_YYYYMMDD_HHMMSS.keras`, sort by mtime descending, return newest if any.
  3. **Legacy:** If `model_dir / (stem + ".keras")` exists -> return it.
  4. Otherwise return `None` -> API returns **404** with a message that includes the exact path that was checked (e.g. "Looked in .../data/models/box_detector for ..."). This makes it clear the API did not find files in that directory; common causes are the API container not sharing the same `data` volume as the worker, or `DATA_DIR` / `BOX_DETECTOR_MODEL_PATH` pointing elsewhere.

**Used by:** The API's `_box_detector_load_path()` is used internally where path resolution is needed. Evaluate and preview run in the **task container**; the client gets results via `GET /api/tasks/{task_id}` (for evaluation tasks) or `GET /api/extract/training/preview/latest` (for the automatically updated training preview).

If the API and worker run in different containers and do not share the same `data` volume, the task worker will not see model files -> evaluation tasks fail with a clear error. The task worker resolves the load path the same way (same `model_dir` and stem).

---

## 6. Evaluation tasks and automatic preview

**One-off evaluation tasks:** **`POST /api/extract/training/evaluate`** and **`POST /api/extract/training/preview`** create an evaluation task and return `{ task_id }`; the client polls `GET /api/tasks/{task_id}` for results and `model_format`. The task worker loads the model, runs evaluate or preview, and writes results to Redis.

**Automatic training preview:** During an active box detector training task, the worker's background eval loop (every 10s) loads the current checkpoint (`_current.keras`), runs it on the test set for metrics and for preview (predicted origins per test image), and writes to Redis: `task:{task_id}:eval` (metrics), `task:{task_id}:latest_preview` and `extract:training:latest_preview` (items, scale_regular, scale_blueprint). When training completes, the worker runs preview once more for the final model and writes the same preview keys. The frontend polls **`GET /api/extract/training/preview/latest`** and displays the latest preview; no manual "Run preview" is required. Task status `GET /api/tasks/{task_id}` also includes `latest_preview` when present.

---

## 7. Frontend Flow

**Training tab** (`ExtractTraining.tsx`):

- "Start training" -> `POST /api/extract/training/start` -> get `task_id` -> poll `GET /api/tasks/{task_id}` every 2s.
- Displays status (pending / processing / completed / failed / cancelled), progress (epoch X / Y), and partial/final results (loss, test MAE, etc.).
- When status is processing and `latest_eval` is present (from worker's eval thread -> Redis -> task status), shows a small "test set" metrics block with a countdown.

**Training preview** (`TrainingPreview.tsx`):

- Polls **`GET /api/extract/training/preview/latest`** periodically (e.g. every 2.5s). The worker writes the latest preview to Redis during training (eval loop) and on training completion; the API serves it from this endpoint.
- When no preview is available yet: shows "Run training to see preview."
- When preview data is returned: gets `items` (test set with pred_x, pred_y in **cropped** image space), `scale_regular`, `scale_blueprint`; displays prev/next and for the current item:
  - Image URL: `getScreenshotUrl(item.filename, item.subdir, { crop: true })` so the served image is the cropped view (matches origin/pred coords).
  - Two box requests: `fetchBoxes(item.origin_x, item.origin_y, ...)` (ground truth) and `fetchBoxes(item.pred_x, item.pred_y, ...)` (prediction) -> `POST /api/extract/boxes` to get box geometry, then draws SVG overlays.
- Image load error: shows "Screenshot failed to load. Check API base URL (e.g. VITE_API_BASE_URL) if using Docker."

---

## 8. Summary Diagram

```
Frontend                    API (extract)              Redis                    Worker                     Processor / Disk
   |                             |                       |                         |                                |
   | POST /training/start        |                       |                         |                                |
   |----------------------------->|                       |                         |                                |
   |                             | create_training_task   |                         |                                |
   |                             |----------------------->|                         |                                |
   |                             | rpush training_tasks   |                         |                                |
   |<-----------------------------|                       |                         |                                |
   | { task_id }                  |                       |                         |                                |
   |                             |                       |    brpop training_tasks |                                |
   | GET /tasks/{id} (poll)       |                       |<-------------------------|                                |
   |----------------------------->|                       |                         | set CURRENT_TASK_KEY           |
   |                             | hgetall task:meta      |                         | process_training_task()         |
   |                             |<-----------------------|------------------------>|                                |
   |                             |                       |                         | start eval thread              |
   |                             |                       |                         | training_processor.process()  |
   |                             |                       |                         |-------------------------------->|
   |                             |                       |                         |   per epoch: fit, save _current.keras
   |                             |                       |                         |   end: save timestamped + .keras
   |                             |                       |                         |<--------------------------------|
   |                             |                       | update_task_status      |                                |
   |                             |                       |<-------------------------|                                |
   | GET /training/preview       |                       |                         |                                |
   |----------------------------->|                       |                         |                                |
   |                             | _box_detector_load_path() -> _current or timestamped or legacy
   |                             | load_model, predict    |                         |                                |
   |<-----------------------------|                       |                         |                                |
   | { items }                    |                       |                         |                                |
   | GET /screenshots/{file}      |                       |                         |                                |
   |----------------------------->| FileResponse          |                         |                                |
   |<-----------------------------|                       |                         |                                |
```

---

## 9. Files Touched

| Area            | File(s) |
|-----------------|--------|
| Training start  | `api/routes/extract.py`, `api/services/task_service.py` |
| Task status     | `api/routes/tasks.py`, `api/services/task_service.py` |
| Worker loop     | `task/worker.py` (brpop, process_training_task, _eval_loop) |
| Training logic  | `task/processors/box_detector_processor.py` (process, save checkpoint + final) |
| Model path      | `api/routes/extract.py` (_box_detector_load_path) |
| Evaluate/Preview| `api/routes/extract.py` (training_evaluate, training_preview) |
| Frontend        | `frontend/src/components/ExtractTraining.tsx`, `TrainingPreview.tsx`, `frontend/src/api/extract.ts` |
