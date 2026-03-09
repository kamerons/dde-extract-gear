# Training task (architecture)

## Purpose

Neural network training runs as a **task** in the existing task worker, using the same Redis-backed pattern as recommendation tasks. The **box detector** is the first implemented model; stat-type and stat-value classifiers will use the same pattern later.

## Concepts

### Queues and worker design

- **One subprocess per unit of work:** The main process (orchestrator) is the only one that talks to Redis: it pops from **both** `training_tasks` and `recommendation_tasks` (`brpop([training_tasks, recommendation_tasks], ...)`). At most one training or one recommendation runs at a time. Each unit of work runs in a **separate subprocess** (`python -m task.run_task <type> '<payload>'`). When that subprocess exits, process and GPU memory are fully released, avoiding OOM and fragmentation. When a training subprocess returns "suspended" (preview-epoch boundary with pending evaluation), the orchestrator drains `evaluation_tasks` by running each evaluation task in its own subprocess, then starts a new training subprocess with `resume_from_epoch` and `resume_from_existing=True`. A key `training_current_task_id` identifies the active training task; `recommendation_current_task_id` the active recommendation task. When a new training (or recommendation) is created, only that type's current task is cancelled; the other type's queue is not cleared so the other type can wait in queue.
- **Training queue:** Payload includes `task_id` and `model_type` (e.g. `box_detector`).

### Payload

- The task payload includes `task_id` and `model_type` (e.g. `box_detector`). The worker dispatches to the appropriate processor by model type.

### Processor

- A **training processor** (e.g. `BoxDetectorProcessor`) loads data from `data/` according to [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md). For the box detector:
  - At run start, labeled screenshots (with `.txt` origins) are scanned and split into train/test (deterministic; test set is fixed for the whole run).
  - **Augmentation** (shift + fill) is applied in-process during training; see [shared/box_detector_augment.py](../shared/box_detector_augment.py). No separate augmentation script is used.
  - **Incremental data**: at the start of each epoch, the processor re-scans the labeled dirs; new (image, .txt) pairs are added to the training set for that epoch, so labels added from the front-end while training is running are included automatically.
  - Training runs for a **fixed number of epochs** (config: `TRAINING_EPOCHS`). Progress (epoch, loss, accuracy) is written to Redis so the front-end can display it. At preview epochs (and the last epoch) the processor saves the current model to a `_current` checkpoint path; at those boundaries it may yield so the worker can run evaluation tasks, then resume from the checkpoint. The processor checks a cancellation flag between epochs.
  - On completion (or when stopped), the model is saved to the path given by `BOX_DETECTOR_MODEL_PATH`.

### Triggering

- The user starts training from the Extract config UI (POST `/api/extract/training/start`). Training can be stopped via POST `/api/extract/training/stop`.

### Evaluation

- During an active box detector training task, evaluation (test-set metrics and preview) runs **only when a preview epoch is reached** (i.e. when `epoch % preview_every_n_epochs == 0`). The training processor computes metrics and builds the preview at those epochs and notifies the worker via callbacks; the worker writes to Redis (`task:{task_id}:eval`, `task:{task_id}:latest_preview`). The front-end shows these when polling `GET /api/tasks/{task_id}` (response includes `latest_eval` and `latest_preview` when present).
- **Evaluation tasks:** Manual evaluate and preview run as **tasks** in the task container. The client calls `POST /api/extract/training/evaluate` or `POST /api/extract/training/preview`; the API enqueues an evaluation task and returns `task_id`. The client polls `GET /api/tasks/{task_id}`; the response includes `results` and `model_format` (e.g. `.keras` or `HDF5`). See `task/processors/evaluation_processor.py`.

## Interaction with API and front-end

- The **front-end** sends labels to the API (e.g. box coordinates for screenshots). The API persists them into the `data/labeled/` tree. The user starts a training task manually; that task re-scans each epoch and picks up new labels without starting a new run.
- The **task worker** (orchestrator) pops from queues and runs each task in a subprocess; subprocesses write status and results to Redis. The front-end polls `GET /api/tasks/{task_id}` to show progress and accuracy.
