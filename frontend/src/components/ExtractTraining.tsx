import { useCallback, useEffect, useRef, useState } from 'react';
import {
  startTraining,
  startTrainingResumingFromExisting,
  stopTraining,
  getTrainingTaskStatus,
  getExtractConfig,
  getTrainingDataCounts,
  listModels,
  startModelEvaluationTask,
  type TrainingTaskStatus,
  type EvaluateResponse,
  type TrainingPreviewResponse,
  type ExtractConfigResponse,
  type TrainingDataCountsResponse,
  type ModelOption,
  type ModelScope,
} from '../api/extract';
import { OriginScaleEditor } from './OriginScaleEditor';
import { TrainingPreview } from './TrainingPreview';
import { AccuracyStats } from './AccuracyStats';

const TRAINING_POLL_INTERVAL_MS = 2000;
const DEFAULT_PREVIEW_EVERY_N_EPOCHS = 20;
const DEFAULT_PREVIEW_EXPECTED_DURATION_MS = 10000;
const EVAL_COUNTDOWN_SIZE = 56;
const EVAL_COUNTDOWN_STROKE = 4;
const EVAL_COUNTDOWN_R = (EVAL_COUNTDOWN_SIZE - EVAL_COUNTDOWN_STROKE) / 2;
const EVAL_COUNTDOWN_CIRCUMFERENCE = 2 * Math.PI * EVAL_COUNTDOWN_R;

function EvalCountdownCircle({ progress }: { progress: number }) {
  const offset = EVAL_COUNTDOWN_CIRCUMFERENCE * (1 - Math.min(1, progress));
  return (
    <svg
      className="extract-config-eval-countdown"
      width={EVAL_COUNTDOWN_SIZE}
      height={EVAL_COUNTDOWN_SIZE}
      viewBox={`0 0 ${EVAL_COUNTDOWN_SIZE} ${EVAL_COUNTDOWN_SIZE}`}
      aria-hidden
    >
      <circle
        className="extract-config-eval-countdown-bg"
        cx={EVAL_COUNTDOWN_SIZE / 2}
        cy={EVAL_COUNTDOWN_SIZE / 2}
        r={EVAL_COUNTDOWN_R}
        fill="none"
        strokeWidth={EVAL_COUNTDOWN_STROKE}
      />
      <circle
        className="extract-config-eval-countdown-fill"
        cx={EVAL_COUNTDOWN_SIZE / 2}
        cy={EVAL_COUNTDOWN_SIZE / 2}
        r={EVAL_COUNTDOWN_R}
        fill="none"
        strokeWidth={EVAL_COUNTDOWN_STROKE}
        strokeDasharray={EVAL_COUNTDOWN_CIRCUMFERENCE}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${EVAL_COUNTDOWN_SIZE / 2} ${EVAL_COUNTDOWN_SIZE / 2})`}
      />
    </svg>
  );
}

type ModelSubTab = 'box_detector' | 'type' | 'digit';

function evalResponseKey(e: EvaluateResponse): string {
  return `${e.test_mae_x}-${e.test_mae_y}-${e.accuracy_within_5px}`;
}

export function ExtractTraining() {
  const [modelSubTab, setModelSubTab] = useState<ModelSubTab>('box_detector');
  const [extractConfig, setExtractConfig] = useState<ExtractConfigResponse | null>(null);
  const [trainingTaskId, setTrainingTaskId] = useState<string | null>(null);
  const [trainingStatus, setTrainingStatus] = useState<TrainingTaskStatus['status'] | null>(null);
  const [trainingProgress, setTrainingProgress] = useState<{ evaluated: number; total_planned: number } | null>(null);
  const [trainingResults, setTrainingResults] = useState<Record<string, number | string> | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [latestEval, setLatestEval] = useState<EvaluateResponse | null>(null);
  const [latestPreview, setLatestPreview] = useState<TrainingPreviewResponse | null>(null);
  const [previewWaitStart, setPreviewWaitStart] = useState<number | null>(null);
  const [circleProgress, setCircleProgress] = useState(0);
  const [trainingDataCounts, setTrainingDataCounts] = useState<TrainingDataCountsResponse | null>(null);
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [loadedModelMetrics, setLoadedModelMetrics] = useState<EvaluateResponse | null>(null);
  const [loadedModelResults, setLoadedModelResults] = useState<TrainingPreviewResponse | null>(null);
  const [loadingModelMetrics, setLoadingModelMetrics] = useState(false);
  const [loadingModelResults, setLoadingModelResults] = useState(false);
  const [loadedModelError, setLoadedModelError] = useState<string | null>(null);
  const [modelEvaluationTaskId, setModelEvaluationTaskId] = useState<string | null>(null);
  const modelEvaluationTaskIdRef = useRef<string | null>(null);
  const trainingPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const modelEvalPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const modelEvalRequestIdRef = useRef(0);
  const prevEvalKeyRef = useRef<string | null>(null);
  const lastEpochWithPreviewRef = useRef<number>(-1);
  const previewWaitStartRef = useRef<number | null>(null);
  const taskPreviewExpectedDurationMsRef = useRef<number | null>(null);

  useEffect(() => {
    getExtractConfig().then(setExtractConfig).catch(() => {});
  }, []);

  const loadTrainingDataCounts = useCallback(() => {
    getTrainingDataCounts().then(setTrainingDataCounts).catch(() => setTrainingDataCounts(null));
  }, []);

  useEffect(() => {
    if (modelSubTab === 'box_detector') {
      loadTrainingDataCounts();
    }
  }, [modelSubTab, loadTrainingDataCounts]);

  const showLoadedModelMetrics =
    modelSubTab === 'box_detector' &&
    (trainingStatus !== 'pending' && trainingStatus !== 'processing');

  useEffect(() => {
    if (!showLoadedModelMetrics || modelSubTab !== 'box_detector') return;
    listModels()
      .then((list) => {
        setModelOptions(list);
        setSelectedModelId((prev) => {
          if (list.length === 0) return null;
          if (prev && list.some((m) => m.id === prev)) return prev;
          const current = list.find((m) => m.is_current);
          return current ? current.id : list[0].id;
        });
      })
      .catch(() => setModelOptions([]));
  }, [showLoadedModelMetrics, modelSubTab]);

  useEffect(() => {
    if (!showLoadedModelMetrics || selectedModelId == null) {
      setLoadedModelMetrics(null);
      setLoadedModelResults(null);
      setLoadedModelError(null);
      modelEvaluationTaskIdRef.current = null;
      setModelEvaluationTaskId(null);
      if (modelEvalPollRef.current) {
        clearInterval(modelEvalPollRef.current);
        modelEvalPollRef.current = null;
      }
      return;
    }
    setLoadedModelError(null);
    setLoadingModelMetrics(true);
    setLoadingModelResults(true);
    const requestId = ++modelEvalRequestIdRef.current;
    startModelEvaluationTask(selectedModelId, 'all')
      .then(({ task_id }) => {
        if (requestId !== modelEvalRequestIdRef.current) return;
        modelEvaluationTaskIdRef.current = task_id;
        setModelEvaluationTaskId(task_id);
      })
      .catch((e) => {
        if (requestId !== modelEvalRequestIdRef.current) return;
        setLoadedModelMetrics(null);
        setLoadedModelResults(null);
        setLoadedModelError(e instanceof Error ? e.message : 'Failed to start model evaluation');
        setLoadingModelMetrics(false);
        setLoadingModelResults(false);
      });
  }, [showLoadedModelMetrics, selectedModelId]);

  useEffect(() => {
    if (!modelEvaluationTaskId) return;
    const taskId = modelEvaluationTaskId;
    const poll = async () => {
      try {
        const res = await getTrainingTaskStatus(taskId);
        if (modelEvaluationTaskIdRef.current !== taskId) return;
        if (res.status === 'completed' && res.results) {
          const r = res.results as {
            metrics?: EvaluateResponse;
            items?: TrainingPreviewResponse['items'];
            scale_regular?: number;
            scale_blueprint?: number;
          };
          if (modelEvalPollRef.current) {
            clearInterval(modelEvalPollRef.current);
            modelEvalPollRef.current = null;
          }
          modelEvaluationTaskIdRef.current = null;
          setModelEvaluationTaskId(null);
          setLoadedModelMetrics(r.metrics ?? null);
          setLoadedModelResults(
            r.items != null
              ? {
                  items: r.items,
                  scale_regular: Number(r.scale_regular) || 1,
                  scale_blueprint: Number(r.scale_blueprint) || 1,
                }
              : null
          );
          if (r.metrics == null && (r.items == null || r.items.length === 0)) {
            setLoadedModelError('No metrics or results for this model.');
          }
          setLoadingModelMetrics(false);
          setLoadingModelResults(false);
        } else if (res.status === 'failed') {
          if (modelEvalPollRef.current) {
            clearInterval(modelEvalPollRef.current);
            modelEvalPollRef.current = null;
          }
          modelEvaluationTaskIdRef.current = null;
          setModelEvaluationTaskId(null);
          setLoadedModelMetrics(null);
          setLoadedModelResults(null);
          setLoadedModelError(res.error ?? 'Model evaluation failed');
          setLoadingModelMetrics(false);
          setLoadingModelResults(false);
        }
      } catch {
        // keep polling
      }
    };
    poll();
    modelEvalPollRef.current = setInterval(poll, TRAINING_POLL_INTERVAL_MS);
    return () => {
      if (modelEvalPollRef.current) {
        clearInterval(modelEvalPollRef.current);
        modelEvalPollRef.current = null;
      }
    };
  }, [modelEvaluationTaskId]);

  const handleStartTraining = useCallback(async () => {
    setTrainingError(null);
    setTrainingResults(null);
    setLatestEval(null);
    setLatestPreview(null);
    setPreviewWaitStart(null);
    prevEvalKeyRef.current = null;
    lastEpochWithPreviewRef.current = -1;
    taskPreviewExpectedDurationMsRef.current = null;
    try {
      const { task_id } = await startTraining();
      setTrainingTaskId(task_id);
      setTrainingStatus('pending');
      setTrainingProgress(null);
    } catch (e) {
      setTrainingError(e instanceof Error ? e.message : 'Failed to start training');
    }
  }, []);

  const handleStartTrainingResuming = useCallback(async () => {
    setTrainingError(null);
    setTrainingResults(null);
    setLatestEval(null);
    setLatestPreview(null);
    setPreviewWaitStart(null);
    prevEvalKeyRef.current = null;
    lastEpochWithPreviewRef.current = -1;
    taskPreviewExpectedDurationMsRef.current = null;
    try {
      const { task_id } = await startTrainingResumingFromExisting();
      setTrainingTaskId(task_id);
      setTrainingStatus('pending');
      setTrainingProgress(null);
    } catch (e) {
      setTrainingError(e instanceof Error ? e.message : 'Failed to start training');
    }
  }, []);

  const handleStopTraining = useCallback(async () => {
    setTrainingError(null);
    try {
      await stopTraining();
    } catch (e) {
      setTrainingError(e instanceof Error ? e.message : 'Failed to stop training');
    }
  }, []);

  const previewEveryN = extractConfig?.preview_every_n_epochs ?? DEFAULT_PREVIEW_EVERY_N_EPOCHS;

  useEffect(() => {
    if (!trainingTaskId || (trainingStatus !== 'pending' && trainingStatus !== 'processing')) return;
    const taskId = trainingTaskId;
    const poll = async () => {
      try {
        const res = await getTrainingTaskStatus(taskId);
        setTrainingStatus(res.status);
        if (res.progress) setTrainingProgress(res.progress);
        if (res.results) setTrainingResults(res.results as Record<string, number | string>);
        if (res.latest_eval != null) {
          const key = evalResponseKey(res.latest_eval);
          if (prevEvalKeyRef.current !== key) {
            prevEvalKeyRef.current = key;
            setLatestEval(res.latest_eval);
          }
        }
        const evaluated = res.progress?.evaluated ?? 0;
        const atPreviewEpoch = evaluated > 0 && evaluated % previewEveryN === 0;
        const hasPreview =
          res.latest_preview != null &&
          Array.isArray(res.latest_preview.items) &&
          res.latest_preview.items.length > 0;
        if (hasPreview) {
          if (atPreviewEpoch && lastEpochWithPreviewRef.current < evaluated) {
            const waitStart = previewWaitStartRef.current;
            if (typeof waitStart === 'number') {
              const elapsed = Date.now() - waitStart;
              console.info(`[ExtractTraining] Preview received in ${elapsed} ms`);
            }
            lastEpochWithPreviewRef.current = evaluated;
            previewWaitStartRef.current = null;
            setPreviewWaitStart(null);
          }
          setLatestPreview(res.latest_preview ?? null);
        }
        if (atPreviewEpoch && lastEpochWithPreviewRef.current < evaluated) {
          const now = Date.now();
          if (previewWaitStartRef.current == null) {
            previewWaitStartRef.current = now;
            setPreviewWaitStart(now);
          }
        }
        if (res.preview_expected_duration_ms != null) {
          taskPreviewExpectedDurationMsRef.current = res.preview_expected_duration_ms;
        }
        if (res.error) setTrainingError(res.error);
        if (res.status === 'completed' || res.status === 'failed' || res.status === 'cancelled' || res.status === 'not_found') {
          setTrainingTaskId(null);
        }
      } catch {
        // keep polling
      }
    };
    poll();
    const id = setInterval(poll, TRAINING_POLL_INTERVAL_MS);
    trainingPollRef.current = id;
    return () => {
      clearInterval(id);
      trainingPollRef.current = null;
    };
  }, [trainingTaskId, trainingStatus, previewEveryN]);

  useEffect(() => {
    if (trainingStatus !== 'processing' || !trainingProgress) {
      setCircleProgress(0);
      return;
    }
    const N = previewEveryN;
    const evaluated = trainingProgress.evaluated;
    const epochInCycle = evaluated % N;
    const epochProgress = N > 0 ? epochInCycle / N : 0;
    const waiting = evaluated > 0 && evaluated % N === 0 && lastEpochWithPreviewRef.current < evaluated;

    if (waiting && previewWaitStart != null) {
      const tick = () => {
        const expectedMs =
          taskPreviewExpectedDurationMsRef.current ??
          extractConfig?.preview_expected_duration_ms ??
          DEFAULT_PREVIEW_EXPECTED_DURATION_MS;
        const elapsed = Date.now() - previewWaitStart;
        const waitProgress = Math.min(1, elapsed / expectedMs);
        setCircleProgress(0.8 + 0.2 * waitProgress);
      };
      tick();
      const id = setInterval(tick, 100);
      return () => clearInterval(id);
    }
    setCircleProgress(0.8 * epochProgress);
    return undefined;
  }, [trainingStatus, trainingProgress, previewEveryN, extractConfig?.preview_expected_duration_ms, previewWaitStart]);

  return (
    <div className="configuration-container extract-config extract-config--training-page">
      <div className="configuration-header extract-config--training-header">
        <h1>Training</h1>
      </div>

      <nav className="extract-config-model-tabs extract-config-model-tabs-top" aria-label="Model type">
        <button
          type="button"
          className={`extract-config-model-tab ${modelSubTab === 'box_detector' ? 'extract-config-model-tab-active' : ''}`}
          onClick={() => setModelSubTab('box_detector')}
          aria-current={modelSubTab === 'box_detector' ? 'page' : undefined}
        >
          Box detector
        </button>
        <button
          type="button"
          className={`extract-config-model-tab ${modelSubTab === 'type' ? 'extract-config-model-tab-active' : ''}`}
          onClick={() => setModelSubTab('type')}
          aria-current={modelSubTab === 'type' ? 'page' : undefined}
        >
          Type detection
        </button>
        <button
          type="button"
          className={`extract-config-model-tab ${modelSubTab === 'digit' ? 'extract-config-model-tab-active' : ''}`}
          onClick={() => setModelSubTab('digit')}
          aria-current={modelSubTab === 'digit' ? 'page' : undefined}
        >
          Digit detection
        </button>
      </nav>

      <div className="extract-config-training-layout">
        <div className="extract-config-training-left">
          <p className="stat-section-label">Labeling</p>
          {modelSubTab === 'box_detector' && (
            <OriginScaleEditor
              showScaleInput={false}
              showSaveOriginButton={true}
              showAugmentPreview={false}
              preferUnlabeledRandom={true}
              onOriginSaved={loadTrainingDataCounts}
              showCroppedAreaOption={true}
            />
          )}
          {(modelSubTab === 'digit' || modelSubTab === 'type') && (
            <p className="extract-config-coming-soon">Coming soon.</p>
          )}
        </div>
        <div className="extract-config-training-right">
          <p className="stat-section-label">Training</p>
          {modelSubTab === 'box_detector' && trainingDataCounts !== null && (
            <div className="extract-config-training-data-block" role="status">
              <p className="extract-config-training-data-summary">
                <strong>{trainingDataCounts.total}</strong> source images ready for training
                {' '}({trainingDataCounts.regular} regular, {trainingDataCounts.blueprint} blueprint)
              </p>
              <p className="extract-config-training-data-augmented">
                ×{trainingDataCounts.augment_count} augmentation → up to{' '}
                <strong>{trainingDataCounts.augmented_samples_per_epoch_max}</strong> augmented samples per epoch
              </p>
            </div>
          )}
          <div className="extract-config-training-actions">
            <button
              type="button"
              className="extract-config-save-button"
              onClick={handleStartTraining}
              disabled={trainingStatus === 'pending' || trainingStatus === 'processing'}
            >
              Start training
            </button>
            <button
              type="button"
              className="extract-config-resume-button"
              onClick={handleStartTrainingResuming}
              disabled={trainingStatus === 'pending' || trainingStatus === 'processing'}
            >
              Start over (resume from model)
            </button>
            <button
              type="button"
              className="extract-config-stop-button"
              onClick={handleStopTraining}
              disabled={trainingStatus !== 'processing'}
            >
              Stop training
            </button>
          </div>
          {trainingStatus === 'pending' && (
            <p className="extract-config-training-status" role="status">
              Training queued…
            </p>
          )}
          {trainingStatus === 'processing' && trainingProgress && (
            <p className="extract-config-training-status" role="status">
              Epoch {trainingProgress.evaluated} / {trainingProgress.total_planned}
              {trainingResults && typeof trainingResults.train_samples === 'number' && typeof trainingResults.test_samples === 'number' && (
                <> — Train: {Number(trainingResults.train_samples)}, Test: {Number(trainingResults.test_samples)} samples</>
              )}
              {trainingResults && typeof trainingResults.loss === 'number' && (
                <> — loss: {Number(trainingResults.loss).toFixed(4)}</>
              )}
              {trainingResults && typeof trainingResults.val_loss === 'number' && (
                <> — val_loss: {Number(trainingResults.val_loss).toFixed(4)}</>
              )}
            </p>
          )}
          {trainingStatus === 'completed' && trainingResults && (
            <div className="extract-config-training-results" role="status">
              <p className="stat-section-label">Last run</p>
              {trainingResults.stopped_early_100 && (
                <p className="extract-config-early-exit-message" role="status">
                  Training stopped early: 100% test accuracy reached.
                </p>
              )}
              {typeof trainingResults.train_samples === 'number' && typeof trainingResults.test_samples === 'number' && (
                <p className="extract-config-training-samples">
                  Train: {Number(trainingResults.train_samples)}, Test: {Number(trainingResults.test_samples)} samples
                </p>
              )}
              {(typeof trainingResults.test_mae_x === 'number' || typeof trainingResults.test_mae_y === 'number') && (
                <ul>
                  {typeof trainingResults.test_mae_x === 'number' && (
                    <li>Test MAE X: {trainingResults.test_mae_x.toFixed(4)}</li>
                  )}
                  {typeof trainingResults.test_mae_y === 'number' && (
                    <li>Test MAE Y: {trainingResults.test_mae_y.toFixed(4)}</li>
                  )}
                </ul>
              )}
              {(typeof trainingResults.accuracy_within_15px === 'number' || typeof trainingResults.accuracy_within_5px === 'number' || typeof trainingResults.accuracy_within_3px === 'number') && (
                <AccuracyStats
                  accuracyWithin15Px={Number(trainingResults.accuracy_within_15px ?? 0)}
                  accuracyWithin5Px={Number(trainingResults.accuracy_within_5px ?? 0)}
                  accuracyWithin3Px={Number(trainingResults.accuracy_within_3px ?? 0)}
                />
              )}
            </div>
          )}
          {trainingStatus === 'failed' && trainingError && (
            <p className="configuration-error" role="alert">
              {trainingError}
            </p>
          )}
          {trainingStatus === 'cancelled' && (
            <p className="extract-config-training-status" role="status">
              Training was cancelled.
            </p>
          )}
          {showLoadedModelMetrics && (
            <div className="extract-config-loaded-model-metrics" role="status">
              <p className="stat-section-label">Loaded model</p>
              <div className="extract-config-model-select-row">
                <label htmlFor="extract-model-select" className="extract-config-model-select-label">
                  Model
                </label>
                <select
                  id="extract-model-select"
                  className="extract-config-model-select"
                  value={selectedModelId ?? ''}
                  onChange={(e) => setSelectedModelId(e.target.value || null)}
                  disabled={modelOptions.length === 0}
                  aria-label="Select model"
                >
                  {modelOptions.length === 0 && (
                    <option value="">No models — run training first</option>
                  )}
                  {modelOptions.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name}
                    </option>
                  ))}
                </select>
              </div>
              {loadedModelError && (
                <p className="extract-config-no-metrics">{loadedModelError}</p>
              )}
              {!loadedModelError && (loadingModelMetrics ? (
                <p className="extract-config-no-metrics">Loading metrics…</p>
              ) : loadedModelMetrics ? (
                <AccuracyStats
                  accuracyWithin15Px={loadedModelMetrics.accuracy_within_15px}
                  accuracyWithin5Px={loadedModelMetrics.accuracy_within_5px}
                  accuracyWithin3Px={loadedModelMetrics.accuracy_within_3px}
                  labelSuffix=" (estimate)"
                  className="extract-config-loaded-stats"
                />
              ) : (
                <p className="extract-config-no-metrics">No metrics for selected model</p>
              ))}
              <TrainingPreview
                fixedPreview={
                  selectedModelId != null
                    ? (loadedModelResults ?? null)
                    : { items: [], scale_regular: 1, scale_blueprint: 1 }
                }
                fixedPreviewLoading={selectedModelId != null && loadingModelResults}
              />
            </div>
          )}
          {trainingStatus === 'processing' && latestEval && (
            <div className="extract-config-evaluate-results" role="status">
              <div className="extract-config-evaluate-results-header">
                <p className="stat-section-label">Test set</p>
                <EvalCountdownCircle progress={circleProgress} />
              </div>
              <AccuracyStats
                accuracyWithin15Px={latestEval.accuracy_within_15px}
                accuracyWithin5Px={latestEval.accuracy_within_5px}
                accuracyWithin3Px={latestEval.accuracy_within_3px}
              />
            </div>
          )}
          {modelSubTab === 'box_detector' && !showLoadedModelMetrics && (
            <TrainingPreview latestPreview={latestPreview} />
          )}
        </div>
      </div>
    </div>
  );
}
