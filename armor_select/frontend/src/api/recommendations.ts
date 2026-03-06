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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
