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

export interface BoxesResponse {
  boxes: ExtractBox[];
}

export interface ExtractConfigResponse {
  regular_scale: number;
  blueprint_scale: number;
  augment_shift_regular: number;
  augment_shift_blueprint: number;
  augment_fill: string;
}

/**
 * Fetch extract pipeline config from the server (scale and augmentation from env).
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
 * List screenshot filenames in the given subdir.
 */
export async function listScreenshots(
  subdir: string = EXTRACT_SUBDIRS.unlabeled
): Promise<{ filenames: string[] }> {
  const params = new URLSearchParams({ subdir });
  const response = await fetch(`${API_BASE_URL}/api/extract/screenshots?${params}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list screenshots: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Return the URL for loading a screenshot image.
 */
export function getScreenshotUrl(
  filename: string,
  subdir: string = EXTRACT_SUBDIRS.unlabeled
): string {
  const params = new URLSearchParams({ subdir });
  return `${API_BASE_URL}/api/extract/screenshots/${encodeURIComponent(filename)}?${params}`;
}

/**
 * Compute region boxes for the first card given origin, scale, and image type.
 * Returns boxes in full-resolution coordinates; scale to 50% in the UI for display.
 */
export async function fetchBoxes(
  originX: number,
  originY: number,
  scale: number,
  imageType: ImageType
): Promise<BoxesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/boxes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin_x: originX,
      origin_y: originY,
      scale,
      image_type: imageType,
    }),
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
  progress?: { evaluated: number; total_planned: number };
  results?: Record<string, unknown>;
  latest_eval?: EvaluateResponse;
  error?: string;
  model_format?: string;
}

export interface EvaluateResponse {
  test_mae_x: number;
  test_mae_y: number;
  accuracy_within_5px: number;
}

/**
 * Start a box detector training task. Poll with getTrainingTaskStatus(task_id).
 */
export async function startTraining(): Promise<TrainingStartResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/training/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_type: 'box_detector' }),
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
}

export interface TrainingPreviewResponse {
  items: TrainingPreviewItem[];
  scale_regular: number;
  scale_blueprint: number;
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
