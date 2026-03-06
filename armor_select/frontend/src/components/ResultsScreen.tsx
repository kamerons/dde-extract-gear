import { useEffect, useRef, useState } from 'react';
import type { BuildPreferences, Recommendation } from '../types';
import { RecommendationCard } from './RecommendationCard';
import {
  getTaskStatus,
  submitInitialPreferencesAsync,
  POLL_INTERVAL_MS,
} from '../api/recommendations';

interface ResultsScreenProps {
  initialPreferences: BuildPreferences;
  onBack: () => void;
}

/** Merge incoming results into existing list: keep existing order, update in place, append new set_ids. */
function mergeRecommendationsBySetId(
  existing: Recommendation[],
  incoming: Recommendation[]
): Recommendation[] {
  const incomingById = new Map<string, Recommendation>();
  for (const rec of incoming) {
    incomingById.set(rec.set_id, rec);
  }
  const result: Recommendation[] = [];
  for (const rec of existing) {
    result.push(incomingById.get(rec.set_id) ?? rec);
  }
  for (const rec of incoming) {
    if (!existing.some((r) => r.set_id === rec.set_id)) {
      result.push(rec);
    }
  }
  return result;
}

export function ResultsScreen({ initialPreferences, onBack }: ResultsScreenProps) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [status, setStatus] = useState<'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'not_found'>('pending');
  const [progress, setProgress] = useState<{ evaluated: number; total_planned: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stoppedRef = useRef(false);

  // Create task when we have preferences and no taskId yet
  useEffect(() => {
    if (!initialPreferences || taskId !== null) return;
    let cancelled = false;
    setStatus('pending');
    submitInitialPreferencesAsync(initialPreferences)
      .then((id) => {
        if (!cancelled) setTaskId(id);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to create task');
          setStatus('failed');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [initialPreferences, taskId]);

  // Poll when we have a taskId
  useEffect(() => {
    if (!taskId) return;
    const currentTaskId: string = taskId;
    stoppedRef.current = false;

    async function poll() {
      while (!stoppedRef.current) {
        try {
          const response = await getTaskStatus(currentTaskId);
          if (stoppedRef.current) return;

          setStatus(response.status);

          if (response.progress) {
            setProgress(response.progress);
          }

          if (response.results?.recommendations) {
            setRecommendations((prev) =>
              mergeRecommendationsBySetId(prev, response.results!.recommendations)
            );
          }

          if (
            response.status === 'completed' ||
            response.status === 'failed' ||
            response.status === 'cancelled' ||
            response.status === 'not_found'
          ) {
            if (response.status === 'failed' && response.error) {
              setError(response.error);
            }
            if (response.status === 'cancelled') {
              setError(response.error ?? 'Task was cancelled');
              setStatus('cancelled');
            }
            if (response.status === 'not_found') {
              setError(response.error ?? 'Task not found');
              setStatus('failed');
            }
            return;
          }
        } catch (err) {
          if (stoppedRef.current) return;
          setError(err instanceof Error ? err.message : 'Failed to fetch task status');
          setStatus('failed');
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
    }

    poll();
    return () => {
      stoppedRef.current = true;
    };
  }, [taskId]);

  const progressPercent =
    progress && progress.total_planned > 0
      ? Math.round((100 * progress.evaluated) / progress.total_planned)
      : null;
  const isCreatingTask = initialPreferences && taskId === null && !error;
  const isProcessing =
    status === 'pending' || status === 'processing' || isCreatingTask;

  if (error && (status === 'failed' || status === 'cancelled')) {
    return (
      <div className="results-container">
        <div className="error-state">
          <h2>Error Loading Recommendations</h2>
          <p>{error}</p>
          <button onClick={onBack} className="back-button">
            Back to Configuration
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="results-container">
      {isProcessing && (
        <div className="progress-toast" role="status" aria-live="polite">
          {isCreatingTask
            ? 'Creating task…'
            : `Evaluating…${progressPercent !== null ? ` ${progressPercent}%` : ''}`}
        </div>
      )}

      <div className="results-header">
        <h1>Armor Recommendations</h1>
        <p className="results-count">
          {recommendations.length === 0 && isProcessing
            ? isCreatingTask
              ? 'Creating task…'
              : 'Evaluating combinations…'
            : `Found ${recommendations.length} recommendation${recommendations.length !== 1 ? 's' : ''}`}
        </p>
        <button onClick={onBack} className="back-button">
          ← Back to Configuration
        </button>
      </div>

      {recommendations.length === 0 && !isProcessing && status === 'completed' && (
        <div className="empty-state">
          <h2>No Recommendations Found</h2>
          <p>No armor sets match your current preferences. Try adjusting your constraints.</p>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="recommendations-grid">
          {recommendations.map((recommendation, index) => (
            <RecommendationCard
              key={recommendation.set_id}
              recommendation={recommendation}
              rank={index + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
