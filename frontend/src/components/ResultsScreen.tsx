import { useEffect, useMemo, useRef, useState } from 'react';
import type { BuildPreferences, Recommendation, SearchMode } from '../types';
import { RecommendationCard } from './RecommendationCard';
import { getStatDisplayName } from '../constants';
import type { StatType } from '../types';
import { ALL_STATS } from '../constants';
import {
  getTaskStatus,
  getRequestFromPreferences,
  submitInitialPreferencesAsync,
  submitTaskWithWeights,
  POLL_INTERVAL_MS,
} from '../api/recommendations';

interface ResultsScreenProps {
  initialPreferences: BuildPreferences;
  initialDataFile?: string;
  /** When provided (e.g. edited on initial config), use these weights for the task instead of deriving from preferences. */
  initialWeights?: Record<string, number>;
  onBack: () => void;
}

interface FormulaConstants {
  ranges: Record<string, [number, number]>;
  stat_types: string[];
  description: string;
}

/** Default formula constants (match backend StatNormalizer) so config pane is populated before task completes. */
const DEFAULT_FORMULA_CONSTANTS: FormulaConstants = {
  description:
    'score = sum( normalize(stat, value) * weight(stat) ); normalize(stat, value) = value / reference_scale(stat), no cap (relative scaling only).',
  stat_types: [...ALL_STATS],
  ranges: {
    base: [0, 150],
    fire: [0, 50],
    electric: [0, 50],
    poison: [0, 50],
    hero_hp: [0, 50],
    hero_dmg: [0, 50],
    hero_rate: [0, 50],
    hero_speed: [0, 25],
    offense: [0, 50],
    defense: [0, 50],
    tower_hp: [0, 50],
    tower_dmg: [0, 50],
    tower_rate: [0, 50],
    tower_range: [0, 50],
  },
};

/** Merge incoming results: update in place by set_id, append new, then sort by score descending. */
function mergeAndSortRecommendations(
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
  result.sort((a, b) => b.score - a.score);
  return result;
}

/** Recalculate score from breakdown when weights change: new_score = sum( contribution/w_old * w_new ). */
function recalcScore(
  rec: Recommendation,
  weightsUsed: Record<string, number>,
  newWeights: Record<string, number>
): number {
  const breakdown = rec.score_breakdown;
  if (!breakdown) return rec.score;
  let score = 0;
  for (const [stat, contribution] of Object.entries(breakdown)) {
    const wOld = weightsUsed[stat];
    if (wOld != null && wOld > 0) {
      const wNew = newWeights[stat] ?? 0;
      score += (contribution / wOld) * wNew;
    }
  }
  return score;
}

export function ResultsScreen({
  initialPreferences,
  initialDataFile,
  initialWeights,
  onBack,
}: ResultsScreenProps) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [status, setStatus] = useState<'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'not_found'>('pending');
  const [progress, setProgress] = useState<{ evaluated: number; total_planned: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [weightsUsed, setWeightsUsed] = useState<Record<string, number> | null>(null);
  const [formulaConstants, setFormulaConstants] = useState<FormulaConstants | null>(null);
  const [localWeights, setLocalWeights] = useState<Record<string, number>>({});
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [compareSelection, setCompareSelection] = useState<[string | null, string | null]>([null, null]);
  const [currentSearchMode, setCurrentSearchMode] = useState<SearchMode>('broad');
  const [selectedBaseSetId, setSelectedBaseSetId] = useState<string | null>(null);
  const stoppedRef = useRef(false);
  const comparisonPanelRef = useRef<HTMLDivElement>(null);

  const handleCompareWith = (setId: string) => {
    setCompareSelection((prev) => {
      if (prev[0] === setId) return [null, prev[1]];
      if (prev[1] === setId) return [prev[0], null];
      if (prev[0] == null) return [setId, null];
      if (prev[1] == null) return [prev[0], setId];
      return [prev[0], setId];
    });
  };

  // When user selects the second piece for comparison, scroll the comparison panel into view
  useEffect(() => {
    if (compareSelection[1] != null) {
      comparisonPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [compareSelection[1]]);

  const initialRequestParams = useMemo(() => {
    if (!initialPreferences) return null;
    const { weights, constraints } = getRequestFromPreferences(initialPreferences);
    return { weights, constraints, dataFile: initialDataFile, limit: 10 };
  }, [initialPreferences, initialDataFile]);

  // Populate weights and formula as soon as we have preferences (so config pane is usable before task completes)
  useEffect(() => {
    if (!initialPreferences) return;
    const weights =
      initialWeights && Object.keys(initialWeights).length > 0
        ? initialWeights
        : getRequestFromPreferences(initialPreferences).weights;
    setWeightsUsed(weights);
    setLocalWeights(weights);
    setFormulaConstants(DEFAULT_FORMULA_CONSTANTS);
  }, [initialPreferences, initialWeights]);

  // Create task when we have preferences and no taskId yet (always broad, no base)
  useEffect(() => {
    if (!initialPreferences || taskId !== null) return;
    let cancelled = false;
    setStatus('pending');
    setCurrentSearchMode('broad');
    const startTask = () => {
      if (initialWeights && Object.keys(initialWeights).length > 0 && initialRequestParams) {
        return submitTaskWithWeights(
          initialWeights,
          initialRequestParams.constraints,
          initialRequestParams.dataFile,
          initialRequestParams.limit,
          'broad',
          null
        );
      }
      return submitInitialPreferencesAsync(initialPreferences, initialDataFile, 'broad', null);
    };
    startTask()
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
  }, [initialPreferences, initialDataFile, initialWeights, initialRequestParams, taskId]);

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
              mergeAndSortRecommendations(prev, response.results!.recommendations)
            );
          }
          if (response.results?.weights_used != null) {
            setWeightsUsed(response.results.weights_used);
            setLocalWeights((prev) =>
              Object.keys(prev).length === 0 ? response.results!.weights_used! : prev
            );
          }
          if (response.results?.formula_constants != null) {
            setFormulaConstants(response.results.formula_constants);
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

  const displayRecommendations = useMemo(() => {
    if (recommendations.length === 0) return [];
    if (
      !weightsUsed ||
      Object.keys(localWeights).length === 0 ||
      recommendations.some((r) => !r.score_breakdown)
    ) {
      return [...recommendations].sort((a, b) => b.score - a.score);
    }
    const sameWeights =
      Object.keys(weightsUsed).length === Object.keys(localWeights).length &&
      Object.keys(weightsUsed).every(
        (k) => (weightsUsed[k] ?? 0) === (localWeights[k] ?? 0)
      );
    if (sameWeights) {
      return [...recommendations].sort((a, b) => b.score - a.score);
    }
    return recommendations
      .map((rec) => ({
        ...rec,
        score: recalcScore(rec, weightsUsed, localWeights),
      }))
      .sort((a, b) => b.score - a.score);
  }, [recommendations, weightsUsed, localWeights]);

  const weightsDiffer =
    weightsUsed != null &&
    Object.keys(localWeights).length > 0 &&
    (Object.keys(weightsUsed).length !== Object.keys(localWeights).length ||
      !Object.keys(weightsUsed).every(
        (k) => (weightsUsed[k] ?? 0) === (localWeights[k] ?? 0)
      ));

  const originalRankBySetId = useMemo(() => {
    if (!weightsDiffer || recommendations.length === 0) return new Map<string, number>();
    const sorted = [...recommendations].sort((a, b) => b.score - a.score);
    const map = new Map<string, number>();
    sorted.forEach((r, i) => map.set(r.set_id, i + 1));
    return map;
  }, [recommendations, weightsDiffer]);

  const recommendationsById = useMemo(() => {
    const map = new Map<string, Recommendation>();
    recommendations.forEach((r) => map.set(r.set_id, r));
    return map;
  }, [recommendations]);

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

  const statTypesForWeights = formulaConstants?.stat_types ?? ALL_STATS;

  const handleRecalculate = () => {
    if (!initialRequestParams || isRecalculating) return;
    stoppedRef.current = true;
    setError(null);
    setIsRecalculating(true);
    const baseInfo = currentSearchMode === 'deep' && selectedBaseSetId ? { setId: selectedBaseSetId } : null;
    submitTaskWithWeights(
      localWeights,
      initialRequestParams.constraints,
      initialRequestParams.dataFile,
      initialRequestParams.limit,
      currentSearchMode,
      baseInfo
    )
      .then((newTaskId) => {
        setTaskId(newTaskId);
        setRecommendations([]);
        setStatus('pending');
        setError(null);
        setWeightsUsed(localWeights);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Recalculate failed');
        setStatus('failed');
      })
      .finally(() => {
        setIsRecalculating(false);
      });
  };

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
        <div className="results-header-actions">
          <button onClick={onBack} className="back-button">
            ← Back to Configuration
          </button>
          {recommendations.length > 0 && !isProcessing && (
            <>
              <button
                type="button"
                className="broad-search-button"
                disabled={isRecalculating}
                onClick={() => {
                  if (!initialRequestParams || isRecalculating) return;
                  stoppedRef.current = true;
                  setError(null);
                  setIsRecalculating(true);
                  setCurrentSearchMode('broad');
                  setRecommendations([]);
                  setStatus('pending');
                  const weights = localWeights && Object.keys(localWeights).length > 0 ? localWeights : getRequestFromPreferences(initialPreferences).weights;
                  submitTaskWithWeights(weights, initialRequestParams.constraints, initialRequestParams.dataFile, initialRequestParams.limit, 'broad', null)
                    .then((newTaskId) => setTaskId(newTaskId))
                    .catch((err) => {
                      setError(err instanceof Error ? err.message : 'Broad search failed');
                      setStatus('failed');
                    })
                    .finally(() => setIsRecalculating(false));
                }}
              >
                Broad search
              </button>
              <button
                type="button"
                className="deep-search-button"
                disabled={selectedBaseSetId == null || isRecalculating}
                title={selectedBaseSetId == null ? 'Select a recommendation as base first (Use as base)' : 'Run deep search around selected base'}
                onClick={() => {
                  if (!initialRequestParams || selectedBaseSetId == null || isRecalculating) return;
                  stoppedRef.current = true;
                  setError(null);
                  setIsRecalculating(true);
                  setCurrentSearchMode('deep');
                  setRecommendations([]);
                  setStatus('pending');
                  const weights = localWeights && Object.keys(localWeights).length > 0 ? localWeights : getRequestFromPreferences(initialPreferences).weights;
                  submitTaskWithWeights(weights, initialRequestParams.constraints, initialRequestParams.dataFile, initialRequestParams.limit, 'deep', { setId: selectedBaseSetId })
                    .then((newTaskId) => setTaskId(newTaskId))
                    .catch((err) => {
                      setError(err instanceof Error ? err.message : 'Deep search failed');
                      setStatus('failed');
                    })
                    .finally(() => setIsRecalculating(false));
                }}
              >
                Deep search from base
              </button>
            </>
          )}
        </div>
      </div>

      {recommendations.length === 0 && !isProcessing && status === 'completed' && (
        <div className="empty-state">
          <h2>No Recommendations Found</h2>
          <p>No armor sets match your current preferences. Try adjusting your constraints.</p>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="results-two-pane">
          <div className="results-left-pane">
            {compareSelection[0] != null && compareSelection[1] != null && (
              <div className="comparison-panel" ref={comparisonPanelRef}>
                <div className="comparison-panel-header">
                  <h3>Comparing armor sets</h3>
                  <button
                    type="button"
                    className="comparison-clear-button"
                    onClick={() => setCompareSelection([null, null])}
                  >
                    Clear comparison
                  </button>
                </div>
                <div className="comparison-cards">
                  {[compareSelection[0], compareSelection[1]].map((setId) => {
                    const rec = displayRecommendations.find((r) => r.set_id === setId);
                    const rank = rec ? displayRecommendations.indexOf(rec) + 1 : 0;
                    return rec ? (
                      <div key={setId} className="comparison-card-slot">
                        <RecommendationCard
                          recommendation={rec}
                          rank={rank}
                          onCompareWith={() => handleCompareWith(setId)}
                          isCompareSelected={true}
                          onSelectAsBase={() => setSelectedBaseSetId(setId)}
                          isBaseSelected={selectedBaseSetId === setId}
                          originalScore={
                            weightsDiffer ? recommendationsById.get(rec.set_id)?.score : undefined
                          }
                          originalRank={
                            weightsDiffer ? originalRankBySetId.get(rec.set_id) : undefined
                          }
                        />
                      </div>
                    ) : null;
                  })}
                </div>
              </div>
            )}
            <div className="recommendations-grid">
              {displayRecommendations.map((recommendation, index) => (
                <RecommendationCard
                  key={recommendation.set_id}
                  recommendation={recommendation}
                  rank={index + 1}
                  onCompareWith={() => handleCompareWith(recommendation.set_id)}
                  isCompareSelected={
                    recommendation.set_id === compareSelection[0] ||
                    recommendation.set_id === compareSelection[1]
                  }
                  onSelectAsBase={() => setSelectedBaseSetId(recommendation.set_id)}
                  isBaseSelected={selectedBaseSetId === recommendation.set_id}
                  originalScore={
                    weightsDiffer ? recommendationsById.get(recommendation.set_id)?.score : undefined
                  }
                  originalRank={
                    weightsDiffer ? originalRankBySetId.get(recommendation.set_id) : undefined
                  }
                />
              ))}
            </div>
          </div>
          <div className="results-config-pane">
            <h3 className="config-pane-title">Score configuration</h3>
            <p className="config-formula-description">
              {formulaConstants?.description ??
                'score = sum( normalize(stat, value) * weight(stat) ); normalize = value / reference_scale, no cap.'}
            </p>
            {formulaConstants?.ranges && (
              <div className="config-ranges">
                <h4 className="config-section-label">Reference scales (read-only)</h4>
                <ul className="config-ranges-list">
                  {statTypesForWeights.map((stat) => {
                    const range = formulaConstants.ranges[stat];
                    if (!range) return null;
                    return (
                      <li key={stat} className="config-range-item">
                        <span className="stat-name">{getStatDisplayName(stat as StatType) ?? stat}</span>
                        <span className="config-range-value">[0, {range[1]}]</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            <div className="config-weights">
              <h4 className="config-section-label">Stat weights (editable)</h4>
              <p className="config-weights-hint">Changing a weight recalculates and re-sorts the list. Click Recalculate to run a new task with the current weights.</p>
              <div className="config-weights-list">
                {statTypesForWeights.map((stat) => (
                  <label key={stat} className="config-weight-item">
                    <span className="config-weight-label">{getStatDisplayName(stat as StatType) ?? stat}</span>
                    <input
                      type="number"
                      min={0}
                      step={0.05}
                      value={localWeights[stat] ?? ''}
                      onChange={(e) => {
                        const v = e.target.value === '' ? undefined : parseFloat(e.target.value);
                        if (v !== undefined && (isNaN(v) || v < 0)) return;
                        setLocalWeights((prev) => ({
                          ...prev,
                          [stat]: v ?? 0,
                        }));
                      }}
                      className="config-weight-input"
                      aria-label={`Weight for ${getStatDisplayName(stat as StatType) ?? stat}`}
                    />
                  </label>
                ))}
              </div>
            </div>
            <div className="config-actions">
              <button
                type="button"
                onClick={handleRecalculate}
                disabled={!initialRequestParams || isRecalculating}
                className="recalculate-button"
              >
                {isRecalculating ? 'Starting…' : 'Recalculate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
