import { useCallback, useEffect, useRef, useState } from 'react';
import {
  startTraining,
  stopTraining,
  getTrainingTaskStatus,
  type TrainingTaskStatus,
  type EvaluateResponse,
} from '../api/extract';
import { OriginScaleEditor } from './OriginScaleEditor';
import { TrainingPreview } from './TrainingPreview';

const TRAINING_POLL_INTERVAL_MS = 2000;
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

const EVAL_COUNTDOWN_DURATION_MS = 10000;

type ModelSubTab = 'box_detector' | 'type' | 'digit';

function evalResponseKey(e: EvaluateResponse): string {
  return `${e.test_mae_x}-${e.test_mae_y}-${e.accuracy_within_5px}`;
}

export function ExtractTraining() {
  const [modelSubTab, setModelSubTab] = useState<ModelSubTab>('box_detector');
  const [trainingTaskId, setTrainingTaskId] = useState<string | null>(null);
  const [trainingStatus, setTrainingStatus] = useState<TrainingTaskStatus['status'] | null>(null);
  const [trainingProgress, setTrainingProgress] = useState<{ evaluated: number; total_planned: number } | null>(null);
  const [trainingResults, setTrainingResults] = useState<Record<string, number | string> | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [latestEval, setLatestEval] = useState<EvaluateResponse | null>(null);
  const [evalCountdownStart, setEvalCountdownStart] = useState<number | null>(null);
  const [evalCountdownProgress, setEvalCountdownProgress] = useState(0);
  const trainingPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevEvalKeyRef = useRef<string | null>(null);

  const handleStartTraining = useCallback(async () => {
    setTrainingError(null);
    setTrainingResults(null);
    setLatestEval(null);
    setEvalCountdownStart(null);
    prevEvalKeyRef.current = null;
    try {
      const { task_id } = await startTraining();
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

  useEffect(() => {
    if (!trainingTaskId || (trainingStatus !== 'pending' && trainingStatus !== 'processing')) return;
    const taskId = trainingTaskId;
    const poll = async () => {
      try {
        const res = await getTrainingTaskStatus(taskId);
        setTrainingStatus(res.status);
        if (res.progress) setTrainingProgress(res.progress);
        if (res.results) setTrainingResults(res.results);
        if (res.latest_eval != null) {
          const key = evalResponseKey(res.latest_eval);
          if (prevEvalKeyRef.current !== key) {
            prevEvalKeyRef.current = key;
            setLatestEval(res.latest_eval);
            setEvalCountdownStart(Date.now());
          }
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
  }, [trainingTaskId, trainingStatus]);

  useEffect(() => {
    if (trainingStatus !== 'processing' || latestEval == null || evalCountdownStart == null) return;
    const tick = () => {
      const elapsed = Date.now() - evalCountdownStart;
      setEvalCountdownProgress(Math.min(1, elapsed / EVAL_COUNTDOWN_DURATION_MS));
    };
    tick();
    const id = setInterval(tick, 100);
    return () => clearInterval(id);
  }, [trainingStatus, latestEval, evalCountdownStart]);

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
            />
          )}
          {(modelSubTab === 'digit' || modelSubTab === 'type') && (
            <p className="extract-config-coming-soon">Coming soon.</p>
          )}
        </div>
        <div className="extract-config-training-right">
          <p className="stat-section-label">Training</p>
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
              <ul>
                {typeof trainingResults.test_mae_x === 'number' && (
                  <li>Test MAE X: {trainingResults.test_mae_x.toFixed(4)}</li>
                )}
                {typeof trainingResults.test_mae_y === 'number' && (
                  <li>Test MAE Y: {trainingResults.test_mae_y.toFixed(4)}</li>
                )}
                {typeof trainingResults.accuracy_within_5px === 'number' && (
                  <li>Accuracy within 5px: {(Number(trainingResults.accuracy_within_5px) * 100).toFixed(2)}%</li>
                )}
              </ul>
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
          {trainingStatus === 'processing' && latestEval && (
            <div className="extract-config-evaluate-results" role="status">
              <div className="extract-config-evaluate-results-header">
                <p className="stat-section-label">Test set</p>
                <EvalCountdownCircle progress={evalCountdownProgress} />
              </div>
              <ul>
                <li>Test MAE X: {latestEval.test_mae_x.toFixed(4)}</li>
                <li>Test MAE Y: {latestEval.test_mae_y.toFixed(4)}</li>
                <li>Accuracy within 5px: {(latestEval.accuracy_within_5px * 100).toFixed(2)}%</li>
              </ul>
            </div>
          )}
          {modelSubTab === 'box_detector' && (
            <TrainingPreview />
          )}
        </div>
      </div>
    </div>
  );
}
