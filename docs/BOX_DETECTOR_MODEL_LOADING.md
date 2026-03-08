# Box detector model loading: summary

This document summarizes how box detector models are saved and loaded, the issues we hit (404 "model not found", Keras "File not found"), and how they were fixed.

---

## 1. Where models live

- **Directory:** `DATA_DIR/models/box_detector/` (e.g. `/app/data/models/box_detector` in Docker).
- **Files:** The trainer writes:
  - `{stem}_current.keras` — checkpoint (updated each epoch during training).
  - `{stem}_YYYYMMDD_HHMMSS.keras` — timestamped final model.
  - `{stem}.keras` — legacy name for the final model.
- **Stem** comes from `BOX_DETECTOR_MODEL_PATH` (e.g. `data/models/box_detector/box_detector_model` → stem `box_detector_model`).

The **task worker** (and only the task worker) loads and runs the box detector model for inference. The API does **not** load the model; evaluate and preview are run as tasks in the task container. The API and task worker must see the same directory (same volume mount in Docker). See [EXTRACT_TRAINING_FLOW.md](EXTRACT_TRAINING_FLOW.md) for the full flow.

**Why the API must not run models:** The API container must not load or run box detector models. Models are trained and saved in the task container, which may use a different Keras/TensorFlow (or backend) version than the API container. Loading a saved model in the API can fail with deserialization errors (e.g. `Conv2D` / `batch_input_shape`). All model loading and inference run only in the **task (worker) container**.

---

## 2. What was going wrong (404 "model not found")

Users saw **404** and the message *"Box detector model not found. Run training first."* even when files were present in `data/models/box_detector/`.

### What we found

1. **Path resolution was correct**  
   Logs showed `load_path=/app/data/models/box_detector/box_detector_model_current.keras` and the file was visible to the API (e.g. via `docker exec ... ls` and the debug endpoint). So the 404 was **not** from "no file at that path."

2. **Keras was failing to load the file**  
   The API calls `keras.models.load_model(load_path)`. Keras raised:
   ```text
   ValueError: File not found: filepath=.../box_detector_model_current.keras.
   Please ensure the file is an accessible `.keras` zip file.
   ```
   So the failure was **inside Keras**, not "file doesn't exist on disk."

3. **The file was not a valid .keras zip**  
   We checked in the container:
   ```bash
   python3 -c "
   import zipfile
   from pathlib import Path
   p = Path('/app/data/models/box_detector/box_detector_model_current.keras')
   print('is_zipfile:', zipfile.is_zipfile(p))
   "
   # is_zipfile: False
   ```
   Keras 3 expects a `.keras` file to be a **zip archive** (with `config.json`, `model.weights.h5`, `metadata.json`, etc.). The on-disk file was ~101 MB and had a `.keras` extension but was **not** a zip (likely HDF5 or another format written with a `.keras` name). So Keras tried to open it as a zip, failed, and reported "File not found."

4. **Why the trainer wrote a non-zip file**  
   The trainer used `model.save(path_str, save_format="keras")` with a fallback to `model.save(path_str)`. In some TensorFlow/Keras versions the fallback writes HDF5 (or another format) even when the path ends in `.keras`, so the resulting file was not the zip format the loader expects.

---

## 3. What we changed

### Trainer: save in the real .keras (zip) format

**File:** `task/processors/box_detector_processor.py`

- We now prefer **`keras.saving.save_model(model, path_str)`**, which writes the native .keras zip format that `load_model()` expects.
- If `keras.saving.save_model` is not available (older TF), we fall back to `model.save(path_str, save_format="keras")` and then `model.save(path_str)`.

**Effect:** New training runs produce proper .keras zip files. Old files (already on disk) are unchanged and will not load until you retrain.

### Task container: loading and format logging

**Files:** `task/processors/evaluation_processor.py`, `task/worker.py`

- **Loading:** All model loading and inference run in the task container on a single thread; the evaluation processor and training use **`_load_box_detector_model(load_path)`** (temp copy, format detection). Training yields at preview-epoch boundaries when evaluation tasks are pending so only one model is on GPU at a time.
- **Logging:** When loading, the worker logs e.g. `Loading box detector model from <path> (format: .keras zip)` or `(format: HDF5)`. **UI:** For evaluation tasks, the worker writes `task:{task_id}:model_format` to Redis; the API includes it in `GET /api/tasks/{task_id}`; the frontend can show "Model format: .keras" or "HDF5".

### API: no model loading

- The API does not load the box detector model. Evaluate, preview, and **model-metrics / model-results** (metrics and per-image results for a selected model) all run in the task container. The client gets results via task status or the latest-preview endpoint. For metrics and results for a specific model, the client calls **POST /api/extract/model-evaluation/start** (with optional `model_id` and `scope`) and polls **GET /api/tasks/{task_id}** until completed; `results` then contain `metrics`, `items`, `scale_regular`, and `scale_blueprint`.

---

## 4. Current flow (short)

1. **Training** (task container only)  
   The processor saves with `keras.saving.save_model()` when available so new checkpoints and final models are valid .keras zip files.

2. **Evaluate / preview** (task container only)  
   The client can call `POST /api/extract/training/evaluate` or `POST .../preview` to run a one-off evaluation task; the API enqueues it and returns `task_id`; the client polls `GET /api/tasks/{task_id}` for results and `model_format`. Evaluation runs on the **same thread** as training: when evaluation tasks are pending, training yields at the next preview-epoch boundary (checkpoint saved, GPU freed), the worker runs evaluation tasks, then training resumes. During training the processor also builds preview at preview epochs and the worker writes it to Redis. The frontend polls `GET /api/extract/training/preview/latest` to get the latest preview and display it; no manual "Run preview" is required.

3. **Model metrics and results** (task container only)  
   To get metrics and per-image results for a specific model (e.g. when the user selects a model in the UI), the client calls **POST /api/extract/model-evaluation/start** with body `{ "model_id": "<id or null>", "scope": "all" | "test" }`. The API enqueues a `model_evaluation` task and returns `task_id`. The client polls **GET /api/tasks/{task_id}**; when `status` is `completed`, `results` contain `metrics`, `items`, `scale_regular`, and `scale_blueprint`. This ensures the model is loaded and run only in the task container, avoiding API/worker library version mismatch.

---

## 5. What you need to do

- **HDF5 models** (file exists but `zipfile.is_zipfile()` is False, e.g. content starts with `\x89HDF`): The task container loads them by copying to a temp `.h5` path, so they work without retraining. New training should still write proper .keras zips (extension-driven save in the trainer).
- **New models:** Run a **new training** (start training and let it complete or at least save a checkpoint). New files should be saved as proper .keras zips and will load in the task container.
- **Verify (optional):** After a new checkpoint exists, you can confirm it's a zip, e.g.:
  ```bash
  docker exec armor_select_task python3 -c "
  import zipfile
  from pathlib import Path
  p = Path('/app/data/models/box_detector/box_detector_model_current.keras')
  print('is_zipfile:', zipfile.is_zipfile(p))
  if zipfile.is_zipfile(p):
      with zipfile.ZipFile(p) as z:
          print('entries:', z.namelist()[:10])
  "
  ```
  The training UI automatically shows the latest preview (polling `GET /api/extract/training/preview/latest`) as the model is updated during and after training.

---

## 6. References

- [EXTRACT_TRAINING_FLOW.md](EXTRACT_TRAINING_FLOW.md) — Full training and preview flow.
- Path resolution in API: `api/routes/extract.py` (`_box_detector_load_path`).
- Loading and format logging: `task/processors/evaluation_processor.py` (`_load_box_detector_model`, `run_evaluate`, `run_preview`, `build_preview_items`).
- Save format: `task/processors/box_detector_processor.py` (`_save_model_native`).
- Latest preview endpoint: `GET /api/extract/training/preview/latest` returns the most recent preview written by the worker's eval loop or on training completion.
