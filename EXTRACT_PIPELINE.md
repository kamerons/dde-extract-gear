# Extract Pipeline Architecture

## Overview

This document outlines the architecture for moving from fake armor data to real game data: collecting screenshots from the game, retraining the neural networks that were never committed, and organizing all training data under a canonical layout. The pipeline is: **collect → locate box → split → classify** (icons + digits), producing the JSON used by the armor selection system.

## Three Steps to a Working Extract Pipeline

### 1. Source data

- A **screenshot collection script** captures images from the user’s screen while they play. See [scripts/SCREENSHOT_COLLECTION.md](scripts/SCREENSHOT_COLLECTION.md).
- The user triggers each capture with a key combination (e.g. **o** then **p**). Images are stored under `data/` according to the layout in [shared/DATA_LAYOUT.md](shared/DATA_LAYOUT.md).

### 2. Box detector

- A new neural network takes a **full screenshot** and outputs:
  - The **top-left** of the gear/card box.
  - A **classification**: type 1 (“regular”) or type 2 (“blueprint”).
- Box **dimensions** are read from a config file (two sizes, one per type).
- Training uses a **limited initial labeled set** plus **ongoing labels from the front-end**; labeling and training happen in the same workflow.
- **Augmentation**: small translations of the image during training.
- A defined portion of labeled data is **reserved as a test set**.

### 3. Two image classifiers

- The legacy **image_splitter** is recreated (sizes and offsets from config, plus box type). It uses the box detector’s output (top-left + type) to crop regions from the screenshot.
- Those crops feed two classifiers, trained via the same **interactive labeling** process:
  - **Stat-type (icon)** classifier: which stat the icon represents.
  - **Stat-value (digit)** classifier: digit (and possibly “blob”) recognition.
- For each of these, a portion of labeled data is **reserved as a test set**.

## Training as a task

Neural network training runs as a **task** in the existing task worker (Redis-backed, same pattern as recommendation tasks). Details: [task/TRAINING_TASK.md](task/TRAINING_TASK.md).

## Data layout

All paths for unlabeled screenshots, labeled screenshots (with box coordinates), and labeled icons/numbers follow the structure in [shared/DATA_LAYOUT.md](shared/DATA_LAYOUT.md). Code in `api/`, `task/`, and `scripts/` should conform to that layout.

## Interactive labeling

Labels and corrections are provided from the **front-end**. The API persists them into the `data/labeled/` tree. As more data is added, training can be re-run (e.g. by enqueueing a training task). The system is designed so that labeling and training can proceed in parallel over time.

## Pipeline flow (high level)

```mermaid
flowchart LR
  Screenshots[Screenshots]
  BoxDetector[Box detector]
  Crops[Crops]
  IconClassifier[Icon classifier]
  DigitClassifier[Digit classifier]
  JSON[collected.json]

  Screenshots --> BoxDetector
  BoxDetector --> Crops
  Crops --> IconClassifier
  Crops --> DigitClassifier
  IconClassifier --> JSON
  DigitClassifier --> JSON
```
