# Training task (architecture)

## Purpose

Neural network training runs as a **task** in the existing task worker, using the same Redis-backed pattern as recommendation tasks. The **box detector** is the first implemented model; stat-type and stat-value classifiers will use the same pattern later.

## Concepts

### Queue

- A single queue `training_tasks` is used; the payload includes `model_type` (e.g. `box_detector`). A key `training_current_task_id` identifies the active training task so the API can cancel it.

### Payload

- The task payload includes `task_id` and `model_type` (e.g. `box_detector`). The worker dispatches to the appropriate processor by model type.

### Processor

- A **training processor** (e.g. `BoxDetectorProcessor`) loads data from `data/` according to [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md). For the box detector:
  - At run start, labeled screenshots (with `.txt` origins) are scanned and split into train/test (deterministic; test set is fixed for the whole run).
  - **Augmentation** (shift + fill) is applied in-process during training; see [shared/box_detector_augment.py](../shared/box_detector_augment.py). No separate augmentation script is used.
  - **Incremental data**: at the start of each epoch, the processor re-scans the labeled dirs; new (image, .txt) pairs are added to the training set for that epoch, so labels added from the front-end while training is running are included automatically.
  - Training runs for a **fixed number of epochs** (config: `TRAINING_EPOCHS`). Progress (epoch, loss, accuracy) is written to Redis so the front-end can display it. After each epoch the processor saves the current model to a `_current` checkpoint path so the worker’s background eval thread can load it. The processor checks a cancellation flag between epochs.
  - On completion (or when stopped), the model is saved to the path given by `BOX_DETECTOR_MODEL_PATH`.

### Triggering

- The user starts training from the Extract config UI (POST `/api/extract/training/start`). Training can be stopped via POST `/api/extract/training/stop`.

### Evaluation

- During an active box detector training task, the worker runs a **background thread** that evaluates the current model (saved after each epoch to a `_current` checkpoint) against the test set **every 10 seconds** and writes metrics to Redis (`task:{task_id}:eval`). The front-end shows these as live metrics without a button when polling `GET /api/tasks/{task_id}` (response includes `latest_eval` when present). Evaluation runs in a separate thread so it does not block training.
- Manual evaluation of the final saved model remains available via GET `/api/extract/training/evaluate` if desired.

## Interaction with API and front-end

- The **front-end** sends labels to the API (e.g. box coordinates for screenshots). The API persists them into the `data/labeled/` tree. The user starts a training task manually; that task re-scans each epoch and picks up new labels without starting a new run.
- The **task worker** listens to both `training_tasks` and the recommendation queue; it runs one task at a time and updates Redis with status and results. The front-end polls `GET /api/tasks/{task_id}` to show progress and accuracy.
