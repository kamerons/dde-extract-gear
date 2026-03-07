# Box detector model loading: summary

This document summarizes how box detector models are saved and loaded, the issues we hit (404 “model not found”, Keras “File not found”), and how they were fixed.

---

## 1. Where models live

- **Directory:** `DATA_DIR/models/box_detector/` (e.g. `/app/data/models/box_detector` in Docker).
- **Files:** The trainer writes:
  - `{stem}_current.keras` — checkpoint (updated each epoch during training).
  - `{stem}_YYYYMMDD_HHMMSS.keras` — timestamped final model.
  - `{stem}.keras` — legacy name for the final model.
- **Stem** comes from `BOX_DETECTOR_MODEL_PATH` (e.g. `data/models/box_detector/box_detector_model` → stem `box_detector_model`).

The API and the task worker must see the same directory (same volume mount in Docker). See [EXTRACT_TRAINING_FLOW.md](EXTRACT_TRAINING_FLOW.md) for the full flow.

---

## 2. What was going wrong (404 “model not found”)

Users saw **404** and the message *“Box detector model not found. Run training first.”* even when files were present in `data/models/box_detector/`.

### What we found

1. **Path resolution was correct**  
   Logs showed `load_path=/app/data/models/box_detector/box_detector_model_current.keras` and the file was visible to the API (e.g. via `docker exec ... ls` and the debug endpoint). So the 404 was **not** from “no file at that path.”

2. **Keras was failing to load the file**  
   The API calls `keras.models.load_model(load_path)`. Keras raised:
   ```text
   ValueError: File not found: filepath=.../box_detector_model_current.keras.
   Please ensure the file is an accessible `.keras` zip file.
   ```
   So the failure was **inside Keras**, not “file doesn’t exist on disk.”

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
   Keras 3 expects a `.keras` file to be a **zip archive** (with `config.json`, `model.weights.h5`, `metadata.json`, etc.). The on-disk file was ~101 MB and had a `.keras` extension but was **not** a zip (likely HDF5 or another format written with a `.keras` name). So Keras tried to open it as a zip, failed, and reported “File not found.”

4. **Why the trainer wrote a non-zip file**  
   The trainer used `model.save(path_str, save_format="keras")` with a fallback to `model.save(path_str)`. In some TensorFlow/Keras versions the fallback writes HDF5 (or another format) even when the path ends in `.keras`, so the resulting file was not the zip format the loader expects.

---

## 3. What we changed

### Trainer: save in the real .keras (zip) format

**File:** `task/processors/box_detector_processor.py`

- We now prefer **`keras.saving.save_model(model, path_str)`**, which writes the native .keras zip format that `load_model()` expects.
- If `keras.saving.save_model` is not available (older TF), we fall back to `model.save(path_str, save_format="keras")` and then `model.save(path_str)`.

**Effect:** New training runs produce proper .keras zip files. Old files (already on disk) are unchanged and will not load until you retrain.

### API: clearer errors and temp-copy workaround

**File:** `api/routes/extract.py`

- **Path resolution:** We resolve `model_dir` and support a “second-chance” resolution from a single directory listing so we don’t 404 when the path is valid but `exists()`/`glob()` were flaky.
- **Loading:** We load via **`_load_box_detector_model(load_path)`**, which copies the chosen file to a **temporary file** under `/tmp` and calls `keras.models.load_model()` on that path. That was added to work around Keras sometimes failing on bind-mounted paths; it also doesn’t fix files that aren’t valid zips.
- **Errors:** When Keras fails to load, we log the exception and return a clear message (e.g. “Model file found at … but Keras failed to load it: …”) instead of the generic “Run training first.”
- **Caching:** Training endpoints send `Cache-Control: no-store` so browsers don’t cache 404s. In dev, `DISABLE_HTTP_CACHE=1` disables caching for all API responses.

### Docs and debugging

- **EXTRACT_TRAINING_FLOW.md** — Updated to describe the 404 message and that it can include the path we looked in.
- **Logging** — The preview endpoint logs path resolution and, on load failure, the Keras error and traceback.
- **`GET /api/extract/training/model-debug`** — Returns resolved paths, stem, and directory listing so you can confirm what the API sees.

---

## 4. Current flow (short)

1. **Resolve path**  
   `_box_detector_load_path()` returns the path to use: `_current.keras` if present, else latest timestamped, else `stem.keras`. If none found, we optionally run a second-chance from the directory listing.

2. **If no path**  
   Return 404 with a message that includes the directory we looked in and optional debug (listing, etc.).

3. **If path found**  
   Call `_load_box_detector_model(load_path)`: copy file to a temp path, `keras.models.load_model(temp_path)`, then delete the temp file. On success, run evaluate or preview; on Keras error, log and return 404/500 with the real error message.

4. **Training**  
   The processor saves with `keras.saving.save_model()` when available so new checkpoints and final models are valid .keras zip files.

---

## 5. What you need to do

- **HDF5 models** (file exists but `zipfile.is_zipfile()` is False, e.g. content starts with `\x89HDF`): The API now loads them by copying to a temp `.h5` path, so they work without retraining. New training should still write proper .keras zips (extension-driven save in the trainer).
- **New models:** Run a **new training** (start training and let it complete or at least save a checkpoint). New files should be saved as proper .keras zips and will load in the API.
- **Verify (optional):** After a new checkpoint exists, you can confirm it’s a zip, e.g.:
  ```bash
  docker exec armor_select_api python3 -c "
  import zipfile
  from pathlib import Path
  p = Path('/app/data/models/box_detector/box_detector_model_current.keras')
  print('is_zipfile:', zipfile.is_zipfile(p))
  if zipfile.is_zipfile(p):
      with zipfile.ZipFile(p) as z:
          print('entries:', z.namelist()[:10])
  "
  ```
  Then use the training preview again; it should load the new model.

---

## 6. References

- [EXTRACT_TRAINING_FLOW.md](EXTRACT_TRAINING_FLOW.md) — Full training and preview flow.
- Path resolution and 404 handling: `api/routes/extract.py` (`_box_detector_load_path`, `_load_box_detector_model`, preview/evaluate endpoints).
- Save format: `task/processors/box_detector_processor.py` (`_save_model_native`).
