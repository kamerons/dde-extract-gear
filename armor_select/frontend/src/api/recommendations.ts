import type { BuildPreferences, Recommendation, RecommendationPiece } from '../types';

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
  results?: RecommendationResponse;
  progress?: { evaluated: number; total_planned: number };
  error?: string;
  created_at?: string;
}

// Use environment variable if set, otherwise use relative URL for Vite proxy in dev
// In production (Docker), this should be set to the API service URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function convertPreferencesToRequest(preferences: BuildPreferences): {
  weights: Record<string, number>;
  constraints: { min: Record<string, number> };
} {
  const weights: Record<string, number> = {};
  const constraints: { min: Record<string, number> } = { min: {} };

  // Convert maximizeStats to weights (equal weight for all maximized stats)
  if (preferences.maximizeStats.length > 0) {
    const weightPerStat = 1.0 / preferences.maximizeStats.length;
    for (const stat of preferences.maximizeStats) {
      weights[stat] = weightPerStat;
    }
  }

  // Convert minConstraints to constraints.min
  for (const [stat, value] of Object.entries(preferences.minConstraints)) {
    if (value !== undefined && value > 0) {
      constraints.min[stat] = value;
    }
  }

  // Note: softCaps are not sent in the initial request - they're discovered reactively
  // ignoreStats are handled by not including them in weights

  return { weights, constraints };
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
 */
export async function submitInitialPreferencesAsync(
  preferences: BuildPreferences
): Promise<string> {
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
  onProgress?: (status: TaskResponse) => void
): Promise<RecommendationResponse> {
  const taskId = await submitInitialPreferencesAsync(preferences);

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
