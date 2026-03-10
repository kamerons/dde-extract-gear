/**
 * Extract pipeline API: screenshots and region boxes.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export type ImageType = 'regular' | 'blueprint';

export const EXTRACT_SUBDIRS = {
  unlabeled: 'unlabeled/screenshots',
  regular: 'labeled/screenshots/regular',
  blueprint: 'labeled/screenshots/blueprint',
} as const;

export interface ExtractBox {
  x: number;
  y: number;
  width: number;
  height: number;
  type: 'card' | 'set' | 'stat' | 'level';
}

/** One segment of translation margin line (cropped pixel coords); arrow is drawn at (x2, y2) (crop edge). */
export interface TranslationMarginLineSegment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface TranslationMarginLines {
  left: TranslationMarginLineSegment;
  top: TranslationMarginLineSegment;
  right: TranslationMarginLineSegment;
  bottom: TranslationMarginLineSegment;
}

export interface BoxesResponse {
  boxes: ExtractBox[];
  translation_margin_lines?: TranslationMarginLines;
}

export interface AugmentShiftBounds {
  x_neg: number;
  x_pos: number;
  y_neg: number;
  y_pos: number;
}

export interface ExtractConfigResponse {
  regular_scale: number;
  blueprint_scale: number;
  augment_shift_regular: AugmentShiftBounds;
  augment_shift_blueprint: AugmentShiftBounds;
  augment_fill: string;
  augment_count: number;
  preview_every_n_epochs: number;
  preview_expected_duration_ms: number;
}

/**
 * Fetch extract pipeline config from the server (scale and augmentation from config.yaml).
 */
export async function getExtractConfig(): Promise<ExtractConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/config`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch extract config: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Save the box origin for the current screenshot to a .txt file next to the image.
 */
export async function saveOrigin(
  filename: string,
  subdir: string,
  originX: number,
  originY: number
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/extract/screenshots/save-origin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename,
      subdir,
      origin_x: originX,
      origin_y: originY,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const body = JSON.parse(text) as { detail?: string };
      if (typeof body.detail === 'string') message = body.detail;
    } catch {
      message = `Failed to save origin: ${response.status} ${text}`;
    }
    throw new Error(message);
  }
}

/**
 * Fetch the saved origin (origin_x, origin_y) for a labeled screenshot.
 * Returns the values stored in the companion .txt file.
 * Throws if the screenshot has no saved origin (e.g. 404).
 */
export async function getScreenshotOrigin(
  filename: string,
  subdir: string
): Promise<{ origin_x: number; origin_y: number }> {
  const params = new URLSearchParams({ subdir });
  const response = await fetch(
    `${API_BASE_URL}/api/extract/screenshots/${encodeURIComponent(filename)}/origin?${params}`
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to get origin: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * List screenshot filenames in the given subdir.
 * For labeled/screenshots/regular and labeled/screenshots/blueprint, the response
 * includes has_origin: string[] (subset of filenames that have a saved origin .txt).
 */
export async function listScreenshots(
  subdir: string = EXTRACT_SUBDIRS.unlabeled
): Promise<{ filenames: string[]; has_origin?: string[] }> {
  const params = new URLSearchParams({ subdir });
  const response = await fetch(`${API_BASE_URL}/api/extract/screenshots?${params}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list screenshots: ${response.status} ${text}`);
  }
  return response.json();
}

export interface TrainingDataCountsResponse {
  /** Number of source images (labeled with .txt). */
  total: number;
  regular: number;
  blueprint: number;
  /** Each source image is expanded to this many augmented samples per epoch. */
  augment_count: number;
  /** total × augment_count; max augmented samples per epoch (before train/test split). */
  augmented_samples_per_epoch_max: number;
}

/**
 * Fetch counts of labeled screenshots (source images with .txt) and augmentation info.
 * Used to show "X images ready for training" and how many augmented samples are used.
 */
export async function getTrainingDataCounts(): Promise<TrainingDataCountsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training-data`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch training data counts: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Return the URL for loading a screenshot image.
 * When crop is true and subdir is labeled/screenshots/regular or blueprint, the image is cropped (matches training preview coords).
 */
export function getScreenshotUrl(
  filename: string,
  subdir: string = EXTRACT_SUBDIRS.unlabeled,
  options?: { crop?: boolean }
): string {
  const params = new URLSearchParams({ subdir });
  if (options?.crop) {
    params.set('crop', '1');
  }
  return `${API_BASE_URL}/api/extract/screenshots/${encodeURIComponent(filename)}?${params}`;
}

// --- Verification (full-card verify on labeled screenshots; runs on task container) ---

export interface VerificationStartResponse {
  task_id: string;
  status: string;
}

/** Debug images (base64 PNG) and OCR text returned when verification includes debug payload. */
export interface VerificationDebug {
  region_set?: string;
  region_level?: string;
  region_stat_crops?: string[];
  preprocess_set?: string;
  preprocess_level?: string;
  preprocess_stat_crops?: string[];
  /** Raw text returned by OCR for the set (armor set) region. */
  ocr_set?: string;
  /** Raw text returned by OCR for the level region (expected format: "1 / 16"). */
  ocr_level?: string;
  /** Error message if OCR failed for the set region (e.g. tesseract not found). */
  ocr_set_error?: string;
  /** Error message if OCR failed for the level region. */
  ocr_level_error?: string;
}

/** Verification result when task completes (from GET /api/tasks/{task_id} results). */
export interface VerificationResponse {
  armor_set: string | null;
  current_level: number | null;
  max_level: number | null;
  stats: Record<string, number>;
  error: string | null;
  debug?: VerificationDebug | null;
}

/**
 * Start full-card verification on a labeled screenshot. Returns task_id.
 * Poll getTrainingTaskStatus(task_id) until status is 'completed' or 'failed';
 * when completed, status.results is VerificationResponse.
 */
export async function verifyScreenshot(
  filename: string,
  subdir: string
): Promise<VerificationStartResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, subdir }),
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const body = JSON.parse(text) as { detail?: string };
      if (typeof body.detail === 'string') message = body.detail;
    } catch {
      message = `Failed to start verification: ${response.status} ${text}`;
    }
    throw new Error(message);
  }
  return response.json();
}

// --- Stat icon labeling (type detection) ---

/**
 * List unlabeled stat icon filenames (PNGs in data/unlabeled/stat_icons).
 */
export async function listUnlabeledStatIcons(): Promise<{ filenames: string[] }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/stat-icons/unlabeled`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list unlabeled stat icons: ${response.status} ${text}`);
  }
  return response.json();
}

export interface StatIconItem {
  filename: string;
  stat_type: string | null;
}

/**
 * List all stat icons (unlabeled and labeled) with current label.
 * Use for navigation and re-labeling; frontend keeps full list and can correct labels.
 */
export async function listAllStatIcons(): Promise<{ items: StatIconItem[] }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/stat-icons/list`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list stat icons: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Return the URL for a stat icon image (served from unlabeled or labeled dir).
 */
export function getStatIconUrl(filename: string): string {
  return `${API_BASE_URL}/api/extract/stat-icons/${encodeURIComponent(filename)}`;
}

/**
 * Save stat icon label: move file to labeled/icons/<statType>/ (new label or re-label).
 */
export async function saveStatIconLabel(filename: string, statType: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/extract/stat-icons/save-label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, stat_type: statType }),
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const body = JSON.parse(text) as { detail?: string };
      if (typeof body.detail === 'string') message = body.detail;
    } catch {
      message = `Failed to save stat icon label: ${response.status} ${text}`;
    }
    throw new Error(message);
  }
}

/**
 * Fetch stat types for the UI (STAT_GROUPS keys + "none").
 */
export async function getStatTypes(): Promise<{ stat_types: string[] }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/stat-types`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch stat types: ${response.status} ${text}`);
  }
  return response.json();
}

// --- Digit labeling ---

export interface DigitItem {
  filename: string;
  digit_label: string | null;
}

/**
 * List all digit images (unlabeled and labeled) with current label.
 */
export async function listAllDigits(): Promise<{ items: DigitItem[] }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/digits/list`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list digits: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Return the URL for a digit image (served from unlabeled or labeled dir).
 */
export function getDigitUrl(filename: string): string {
  return `${API_BASE_URL}/api/extract/digits/${encodeURIComponent(filename)}`;
}

/**
 * Save digit label: move file to labeled/numbers/<digitLabel>/.
 */
export async function saveDigitLabel(filename: string, digitLabel: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/extract/digits/save-label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, digit_label: digitLabel }),
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const body = JSON.parse(text) as { detail?: string };
      if (typeof body.detail === 'string') message = body.detail;
    } catch {
      message = `Failed to save digit label: ${response.status} ${text}`;
    }
    throw new Error(message);
  }
}

/**
 * Compute region boxes for the first card given origin, scale, and image type.
 * Returns boxes in full-resolution coordinates; scale to 50% in the UI for display.
 * When imageWidth and imageHeight are provided, response includes translation_margin_lines (cropped pixel coords).
 */
export async function fetchBoxes(
  originX: number,
  originY: number,
  scale: number,
  imageType: ImageType,
  options?: { imageWidth?: number; imageHeight?: number }
): Promise<BoxesResponse> {
  const body: Record<string, unknown> = {
    origin_x: originX,
    origin_y: originY,
    scale,
    image_type: imageType,
  };
  if (options?.imageWidth != null && options?.imageHeight != null) {
    body.image_width = options.imageWidth;
    body.image_height = options.imageHeight;
  }
  const response = await fetch(`${API_BASE_URL}/api/extract/boxes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch boxes: ${response.status} ${text}`);
  }
  return response.json();
}

// --- Box detector training ---

export interface TrainingStartResponse {
  task_id: string;
  status: string;
}

export interface TrainingStopResponse {
  ok: boolean;
  cancelled: boolean;
  message: string;
}

export interface TrainingTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'not_found';
  task_type?: string;
  /** Set for training tasks: 'box_detector' | 'icon_type' | 'digit_detector'. */
  model_type?: 'box_detector' | 'icon_type' | 'digit_detector';
  progress?: { evaluated: number; total_planned: number };
  /** Includes train_samples, test_samples when present; box detector has accuracy_within_*px, icon_type has val_accuracy/accuracy. */
  results?: Record<string, unknown> & { train_samples?: number; test_samples?: number };
  latest_eval?: EvaluateResponse | IconTypeEvalResponse;
  latest_preview?: TrainingPreviewResponse;
  /** Expected duration in ms for next preview (test set size * ms per image). */
  preview_expected_duration_ms?: number;
  error?: string;
  model_format?: string;
}

/** Box detector eval: pixel MAE and accuracy within N px. */
export interface EvaluateResponse {
  test_mae_x: number;
  test_mae_y: number;
  accuracy_within_15px: number;
  accuracy_within_5px: number;
  accuracy_within_3px: number;
}

/** Icon type (classification) eval: fraction correct. */
export interface IconTypeEvalResponse {
  val_accuracy?: number;
  accuracy?: number;
  train_samples?: number;
  test_samples?: number;
}

export interface ModelOption {
  id: string;
  display_name: string;
  is_current?: boolean;
}

/**
 * List available box detector models for the dropdown.
 */
export async function listModels(): Promise<ModelOption[]> {
  const response = await fetch(`${API_BASE_URL}/api/extract/models`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list models: ${response.status} ${text}`);
  }
  return response.json();
}

export type ModelScope = 'all' | 'test';

/**
 * Start a model evaluation task on the worker (metrics + per-image results).
 * Poll getTrainingTaskStatus(task_id) until status is 'completed' or 'failed'.
 * When completed, results contain metrics, items, scale_regular, scale_blueprint.
 */
export async function startModelEvaluationTask(
  modelId?: string,
  scope: ModelScope = 'all'
): Promise<{ task_id: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/model-evaluation/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id: modelId ?? null, scope }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to start model evaluation: ${response.status} ${text}`);
  }
  return response.json();
}

export interface TrainingParamsResponse {
  training_epochs: number;
  initial_learning_rate: number;
}

/**
 * Fetch training params (epochs, learning rate) for resume defaults.
 * Used to pre-populate the start/resume form; values come from saved file or server defaults.
 */
export async function getTrainingParams(): Promise<TrainingParamsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training/params`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to get training params: ${response.status} ${text}`);
  }
  return response.json();
}

export interface TrainingStartOptions {
  /** Which model to train: box_detector (screenshots), icon_type (stat icon), or digit_detector (digit classification). */
  model_type?: 'box_detector' | 'icon_type' | 'digit_detector';
  training_epochs?: number;
  initial_learning_rate?: number;
}

/**
 * Start a training task (box detector or icon type). Poll with getTrainingTaskStatus(task_id).
 */
export async function startTraining(options?: TrainingStartOptions): Promise<TrainingStartResponse> {
  const body: Record<string, unknown> = { model_type: options?.model_type ?? 'box_detector' };
  if (options?.training_epochs != null) body.training_epochs = options.training_epochs;
  if (options?.initial_learning_rate != null) body.initial_learning_rate = options.initial_learning_rate;
  const response = await fetch(`${API_BASE_URL}/api/extract/training/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to start training: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Start a training task using the existing saved model as initial weights (box_detector only; icon_type builds fresh).
 * Poll with getTrainingTaskStatus(task_id).
 */
export async function startTrainingResumingFromExisting(
  options?: TrainingStartOptions
): Promise<TrainingStartResponse> {
  const body: Record<string, unknown> = {
    model_type: options?.model_type ?? 'box_detector',
    resume_from_existing: true,
  };
  if (options?.training_epochs != null) body.training_epochs = options.training_epochs;
  if (options?.initial_learning_rate != null) body.initial_learning_rate = options.initial_learning_rate;
  const response = await fetch(`${API_BASE_URL}/api/extract/training/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to start training: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Request cancellation of the current training task.
 */
export async function stopTraining(): Promise<TrainingStopResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training/stop`, {
    method: 'POST',
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to stop training: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Get status of any task (recommendation or training) by ID.
 */
export async function getTrainingTaskStatus(taskId: string): Promise<TrainingTaskStatus> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to get task status: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Start an evaluation task. Poll getTrainingTaskStatus(task_id) until completed; then results contain metrics and model_format.
 */
export async function startEvaluateTask(): Promise<{ task_id: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training/evaluate`, {
    method: 'POST',
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to start evaluate: ${response.status} ${text}`);
  }
  return response.json();
}

// --- Training preview (test set with predictions) ---

export interface TrainingPreviewItem {
  filename: string;
  subdir: string;
  origin_x: number;
  origin_y: number;
  pred_x: number;
  pred_y: number;
  /** Precomputed GT boxes in the same coordinate space as the preview image (backend sends so frontend just renders). */
  boxes_gt?: ExtractBox[];
  /** Precomputed predicted boxes in the same coordinate space as the preview image. */
  boxes_pred?: ExtractBox[];
  /** When set, use this as the image src (augmented sample embedded in preview). */
  image_data_url?: string;
  /** 1-based index of this augment for the same source (for display). */
  augment_index?: number;
}

export interface TrainingPreviewResponse {
  items: TrainingPreviewItem[];
  scale_regular: number;
  scale_blueprint: number;
}

/**
 * Get the latest training preview (written automatically during training or on completion).
 * Returns null when no preview is available yet.
 */
export async function getLatestPreview(): Promise<TrainingPreviewResponse | null> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training/preview/latest`);
  if (!response.ok) {
    throw new Error(`Failed to get latest preview: ${response.status}`);
  }
  const data = await response.json();
  if (data == null || !data.items || !Array.isArray(data.items)) {
    return null;
  }
  return {
    items: data.items,
    scale_regular: Number(data.scale_regular) || 1,
    scale_blueprint: Number(data.scale_blueprint) || 1,
  };
}

/**
 * Start a preview task. Poll getTrainingTaskStatus(task_id) until completed; then results contain items, scale_regular, scale_blueprint, and model_format.
 */
export async function startPreviewTask(): Promise<{ task_id: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training/preview`, {
    method: 'POST',
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to start preview: ${response.status} ${text}`);
  }
  return response.json();
}
