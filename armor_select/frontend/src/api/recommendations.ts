import type { BuildPreferences } from '../types';

// Placeholder API response structure matching the architecture
export interface RecommendationResponse {
  recommendations: Array<{
    set_id: string;
    pieces: unknown[];
    current_stats: Record<string, number>;
    upgraded_stats: Record<string, number>;
    effective_stats: Record<string, number>;
    wasted_points: Record<string, number>;
    score: number;
    potential_score: number;
    flexibility_score: number;
  }>;
  incremental_changes?: Array<{
    type: string;
    position: number;
    improvement: number;
    old_piece: unknown;
    new_piece: unknown;
  }>;
}

/**
 * Submit initial build preferences to the server.
 * This is a placeholder function that will be connected to the backend API.
 */
export async function submitInitialPreferences(
  preferences: BuildPreferences
): Promise<RecommendationResponse> {
  // Log preferences for debugging
  console.log('Submitting initial preferences:', preferences);

  // Placeholder: In a real implementation, this would make an HTTP request
  // For now, we'll simulate an API call with a delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Return mock response structure
  return {
    recommendations: [],
    incremental_changes: [],
  };
}
