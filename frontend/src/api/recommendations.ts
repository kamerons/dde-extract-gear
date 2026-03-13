import type {
  BuildPreferences,
  Recommendation,
  RecommendationPiece,
  RecommendationTaskResult,
  SearchBaseInfo,
  SearchMode,
} from '../types';
import { ALL_STATS } from '../constants';

export interface RecommendationResponse {
  recommendations: Recommendation[];
  incremental_changes?: Array<{
    type: string;
    position: number;
    improvement: number;
    old_piece: RecommendationPiece;
    new_piece: RecommendationPiece;
  }>;
}

export interface TaskResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'not_found';
  results?: RecommendationTaskResult;
  progress?: { evaluated: number; total_planned: number };
  error?: string;
  created_at?: string;
}

// Use environment variable if set, otherwise use relative URL for Vite proxy in dev
// In production (Docker), this should be set to the API service URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Fetch list of JSON filenames in data/collected/ for the data-file dropdown.
 */
export async function getDataFiles(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/data-files`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch data files: ${response.status} ${text}`);
  }
  const data: { files: string[] } = await response.json();
  return data.files ?? [];
}

function convertPreferencesToRequest(preferences: BuildPreferences): {
  weights: Record<string, number>;
  constraints: { min: Record<string, number> };
} {
  const weights: Record<string, number> = {};
  const constraints: { min: Record<string, number> } = { min: {} };

  const maximized = preferences.maximizeStats;
  const ignored = new Set(preferences.ignoreStats);
  const numMaximized = maximized.length;

  if (numMaximized > 0) {
    const fullWeight = 1.0 / numMaximized;
    const halfWeight = fullWeight * 0.5;
    for (const stat of ALL_STATS) {
      if (ignored.has(stat)) continue;
      weights[stat] = maximized.includes(stat) ? fullWeight : halfWeight;
    }
  } else {
    const nonIgnored = ALL_STATS.filter((s) => !ignored.has(s));
    const w = nonIgnored.length > 0 ? 1.0 / nonIgnored.length : 0;
    for (const stat of nonIgnored) {
      weights[stat] = w;
    }
  }

  for (const [stat, value] of Object.entries(preferences.minConstraints)) {
    if (value !== undefined && value > 0) {
      constraints.min[stat] = value;
    }
  }

  return { weights, constraints };
}

/**
 * Get weights and constraints from build preferences (e.g. to populate UI before task completes).
 */
export function getRequestFromPreferences(preferences: BuildPreferences): {
  weights: Record<string, number>;
  constraints: { min: Record<string, number> };
} {
  return convertPreferencesToRequest(preferences);
}

/**
 * Start a new recommendation task with explicit weights and constraints.
 * Returns task_id for polling. Use this for "Recalculate" with current config-pane weights.
 */
export async function submitTaskWithWeights(
  weights: Record<string, number>,
  constraints: { min: Record<string, number> },
  dataFile?: string,
  limit: number = 10,
  searchMode: SearchMode = 'broad',
  baseInfo?: SearchBaseInfo | null
): Promise<string> {
  const body: Record<string, unknown> = {
    weights,
    constraints: { min: constraints.min ?? {} },
    limit,
    search_mode: searchMode,
    ...(dataFile ? { data_file: dataFile } : {}),
  };
  if (baseInfo?.setId) {
    body.base_set_id = baseInfo.setId;
  }
  const response = await fetch(`${API_BASE_URL}/api/recommendations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to create recommendation task: ${response.status} ${response.statusText}. ${errorText}`
    );
  }

  const data: { task_id: string; status: string; message?: string } = await response.json();
  return data.task_id;
}

/**
 * Submit initial build preferences to the server.
 */
export async function submitInitialPreferences(
  preferences: BuildPreferences
): Promise<RecommendationResponse> {
  const requestBody = convertPreferencesToRequest(preferences);

  const response = await fetch(`${API_BASE_URL}/api/recommendations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...requestBody,
      limit: 10,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to fetch recommendations: ${response.status} ${response.statusText}. ${errorText}`
    );
  }

  const data: RecommendationResponse = await response.json();
  return data;
}

/**
 * Submit initial build preferences to the server (async version).
 * Returns a task_id that can be polled for results.
 * @param dataFile - Optional filename from data/collected/ (e.g. "sample.json")
 * @param searchMode - "broad" (default) or "deep"
 * @param baseInfo - For deep search, the selected base recommendation (setId).
 */
export async function submitInitialPreferencesAsync(
  preferences: BuildPreferences,
  dataFile?: string,
  searchMode: SearchMode = 'broad',
  baseInfo?: SearchBaseInfo | null
): Promise<string> {
  const requestBody = convertPreferencesToRequest(preferences);
  const body: Record<string, unknown> = {
    ...requestBody,
    limit: 10,
    search_mode: searchMode,
    ...(dataFile ? { data_file: dataFile } : {}),
  };
  if (baseInfo?.setId) {
    body.base_set_id = baseInfo.setId;
  }
  const response = await fetch(`${API_BASE_URL}/api/recommendations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to create task: ${response.status} ${response.statusText}. ${errorText}`
    );
  }

  const data: { task_id: string; status: string; message?: string } = await response.json();
  return data.task_id;
}

/**
 * Poll for task results.
 */
export async function getTaskStatus(taskId: string): Promise<TaskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to get task status: ${response.status} ${response.statusText}. ${errorText}`
    );
  }

  const data: TaskResponse = await response.json();
  return data;
}

export const POLL_INTERVAL_MS = 1500;

/**
 * Submit preferences and poll for results until completed.
 * Polls until the task is completed or failed (no timeout).
 */
export async function submitInitialPreferencesWithPolling(
  preferences: BuildPreferences,
  onProgress?: (status: TaskResponse) => void,
  dataFile?: string
): Promise<RecommendationResponse> {
  const taskId = await submitInitialPreferencesAsync(preferences, dataFile);

  for (;;) {
    const status = await getTaskStatus(taskId);

    if (onProgress) {
      onProgress(status);
    }

    if (status.status === 'completed' && status.results) {
      return status.results;
    }

    if (status.status === 'failed') {
      throw new Error(status.error || 'Task failed');
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}
