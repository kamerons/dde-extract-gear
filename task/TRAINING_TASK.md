# Training task (architecture)

## Purpose

Neural network training runs as a **task** in the existing task worker, using the same Redis-backed pattern as recommendation tasks. This document describes the contract and flow at an architectural level; no implementation is specified here.

## Concepts

### Queue

- A dedicated queue (or queue namespace) exists for training jobs. Options include:
  - Separate queues per model, e.g. `train_box_detector`, `train_icon_classifier`, `train_digit_classifier`, or
  - A single queue such as `training_tasks` with a job type (or model id) in the payload.

### Payload

- The task payload must identify **which model** to train (box detector, icon classifier, or digit classifier).
- It may optionally specify a dataset slice, a “since last run” hint, or similar; the exact fields are left to implementation.

### Processor

- A **training processor** (separate from `RecommendationProcessor`) is responsible for:
  - Loading data from `data/` according to [shared/DATA_LAYOUT.md](../shared/DATA_LAYOUT.md).
  - Running training (and optionally validation on the reserved test set).
  - Writing artifacts (e.g. model checkpoints or saved models) to a defined location.
- The worker pulls training tasks from the training queue and invokes this processor.

### Triggering

- Training can be triggered when new labels are submitted from the front-end (e.g. API enqueues a training task after N new labels), or on a schedule, or manually. The doc only describes the intent; the exact policy is an implementation detail.

## Interaction with API and front-end

- The **front-end** sends labels to the API (e.g. box coordinates + class for screenshots, or icon/digit labels for cropped images).
- The **API** persists those labels into the `data/labeled/` tree per the data layout and may enqueue a training task.
- When the **task worker** runs a training task, it reads from the same `data/` layout. No code is specified here; this is the intended flow.
