import { useCallback, useEffect, useState } from 'react';
import {
  listScreenshots,
  getScreenshotUrl,
  verifyScreenshot,
  getTrainingTaskStatus,
  getStatTypes,
  EXTRACT_SUBDIRS,
  type VerificationResponse,
} from '../api/extract';

const VERIFICATION_POLL_INTERVAL_MS = 1500;

interface VerificationItem {
  subdir: string;
  filename: string;
}

function buildLabeledItems(
  regular: { filenames: string[]; has_origin?: string[] },
  blueprint: { filenames: string[]; has_origin?: string[] }
): VerificationItem[] {
  const regularWithOrigin = regular.has_origin ?? regular.filenames;
  const blueprintWithOrigin = blueprint.has_origin ?? blueprint.filenames;
  const regularItems: VerificationItem[] = regularWithOrigin.map((filename) => ({
    subdir: EXTRACT_SUBDIRS.regular,
    filename,
  }));
  const blueprintItems: VerificationItem[] = blueprintWithOrigin.map((filename) => ({
    subdir: EXTRACT_SUBDIRS.blueprint,
    filename,
  }));
  return [...regularItems, ...blueprintItems];
}

/** Stat display order (STAT_GROUPS keys, no "none"). */
const STAT_DISPLAY_ORDER_DEFAULT: string[] = [];

function dataUrlFromBase64(base64: string): string {
  return `data:image/png;base64,${base64}`;
}

export function ExtractVerification() {
  const [items, setItems] = useState<VerificationItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statDisplayOrder, setStatDisplayOrder] = useState<string[]>(STAT_DISPLAY_ORDER_DEFAULT);

  const currentItem = items.length > 0 ? items[currentIndex] ?? null : null;

  useEffect(() => {
    let cancelled = false;
    getStatTypes()
      .then((res) => {
        if (!cancelled) {
          setStatDisplayOrder(res.stat_types.filter((t) => t !== 'none'));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const loadItems = useCallback(async () => {
    try {
      const [resRegular, resBlueprint] = await Promise.all([
        listScreenshots(EXTRACT_SUBDIRS.regular),
        listScreenshots(EXTRACT_SUBDIRS.blueprint),
      ]);
      const list = buildLabeledItems(resRegular, resBlueprint);
      setItems(list);
      setCurrentIndex((prev) => (list.length > 0 && prev >= list.length ? list.length - 1 : prev));
    } catch (e) {
      console.error('Failed to list labeled screenshots', e);
      setItems([]);
      setError(e instanceof Error ? e.message : 'Failed to load screenshot list');
    }
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const runVerification = useCallback(async (subdir: string, filename: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { task_id } = await verifyScreenshot(filename, subdir);
      for (;;) {
        const status = await getTrainingTaskStatus(task_id);
        if (status.status === 'completed' && status.results) {
          setResult(status.results as VerificationResponse);
          break;
        }
        if (status.status === 'failed') {
          setError(status.error ?? 'Verification failed');
          break;
        }
        if (status.status === 'cancelled' || status.status === 'not_found') {
          setError(status.status === 'not_found' ? 'Task not found' : 'Task cancelled');
          break;
        }
        await new Promise((r) => setTimeout(r, VERIFICATION_POLL_INTERVAL_MS));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification failed');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (currentItem) {
      runVerification(currentItem.subdir, currentItem.filename);
    } else {
      setResult(null);
      setError(null);
    }
  }, [currentItem?.subdir, currentItem?.filename, runVerification]);

  const goPrev = useCallback(() => {
    if (items.length === 0) return;
    setCurrentIndex((i) => (i <= 0 ? items.length - 1 : i - 1));
  }, [items.length]);

  const goNext = useCallback(() => {
    if (items.length === 0) return;
    setCurrentIndex((i) => (i >= items.length - 1 ? 0 : i + 1));
  }, [items.length]);

  return (
    <div className="extract-verification">
      <h1>Verification</h1>
      <p className="extract-verification-intro">
        Step through labeled screenshots and run full-card verification (stats, armor set, level).
      </p>
      {items.length === 0 && !error && (
        <p className="extract-verification-empty">
          No labeled screenshots with saved origin. Add screenshots to{' '}
          <code>data/labeled/screenshots/regular</code> or <code>blueprint</code> and save an origin in the Training tab.
        </p>
      )}
      {error && items.length === 0 && (
        <p className="extract-verification-error" role="alert">
          {error}
        </p>
      )}
      {items.length > 0 && (
        <>
          <div className="extract-verification-nav">
            <button
              type="button"
              onClick={goPrev}
              disabled={loading}
              aria-label="Previous screenshot"
            >
              Previous
            </button>
            <span className="extract-verification-counter">
              {currentIndex + 1} / {items.length}
            </span>
            <button
              type="button"
              onClick={goNext}
              disabled={loading}
              aria-label="Next screenshot"
            >
              Next
            </button>
          </div>
          <div className="extract-verification-layout">
            <div className="extract-verification-image-wrap">
              {currentItem && (
                <>
                  <img
                    src={getScreenshotUrl(currentItem.filename, currentItem.subdir, { crop: true })}
                    alt={`Screenshot ${currentItem.filename}`}
                    className="extract-verification-image"
                  />
                  <p className="extract-verification-caption">
                    {currentItem.subdir.split('/').pop()} / {currentItem.filename}
                  </p>
                </>
              )}
            </div>
            <div className="extract-verification-result">
              {loading && <p className="extract-verification-loading">Verifying…</p>}
              {!loading && error && currentItem && (
                <p className="extract-verification-error" role="alert">
                  {error}
                </p>
              )}
              {!loading && result && (
                <div className="extract-verification-result-panel">
                  {result.error && (
                    <p className="extract-verification-partial-error" role="alert">
                      {result.error}
                    </p>
                  )}
                  <dl className="extract-verification-dl">
                    <dt>Armor set</dt>
                    <dd>{result.armor_set ?? '—'}</dd>
                    <dt>Level</dt>
                    <dd>
                      {result.current_level != null && result.max_level != null
                        ? `${result.current_level} / ${result.max_level}`
                        : result.current_level != null
                          ? String(result.current_level)
                          : '—'}
                    </dd>
                  </dl>
                  {(statDisplayOrder.length > 0 || Object.keys(result.stats).length > 0) && (
                    <>
                      <h3 className="extract-verification-stats-heading">Stats</h3>
                      <table className="extract-verification-stats-table">
                        <thead>
                          <tr>
                            <th>Stat</th>
                            <th>Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(statDisplayOrder.length > 0 ? statDisplayOrder : Object.keys(result.stats)).map(
                            (name) => (
                              <tr key={name}>
                                <td>{name}</td>
                                <td>
                                  {result.stats[name] !== undefined ? result.stats[name] : '\u2014'}
                                </td>
                              </tr>
                            )
                          )}
                        </tbody>
                      </table>
                    </>
                  )}
                  {result.debug && (
                    <div className="extract-verification-debug">
                      <h3 className="extract-verification-debug-heading">Regions used</h3>
                      <div className="extract-verification-debug-regions">
                        {result.debug.region_set && (
                          <figure className="extract-verification-debug-figure">
                            <img
                              src={dataUrlFromBase64(result.debug.region_set)}
                              alt="Set region (raw)"
                              className="extract-verification-debug-img"
                            />
                            <figcaption>Set (raw)</figcaption>
                          </figure>
                        )}
                        {result.debug.region_level && (
                          <figure className="extract-verification-debug-figure">
                            <img
                              src={dataUrlFromBase64(result.debug.region_level)}
                              alt="Level region (merged)"
                              className="extract-verification-debug-img"
                            />
                            <figcaption>Level (merged)</figcaption>
                          </figure>
                        )}
                        {result.debug.region_stat_crops && result.debug.region_stat_crops.length > 0 && (
                          <figure className="extract-verification-debug-figure">
                            <div className="extract-verification-debug-stat-grid">
                              {result.debug.region_stat_crops.map((b64, i) => (
                                <img
                                  key={i}
                                  src={dataUrlFromBase64(b64)}
                                  alt={`Stat region ${i + 1}`}
                                  className="extract-verification-debug-img extract-verification-debug-stat-cell"
                                />
                              ))}
                            </div>
                            <figcaption>Stat crops (raw)</figcaption>
                          </figure>
                        )}
                      </div>
                      <h3 className="extract-verification-debug-heading">Preprocessing</h3>
                      <div className="extract-verification-debug-preprocess">
                        {result.debug.preprocess_set && (
                          <figure className="extract-verification-debug-figure">
                            <img
                              src={dataUrlFromBase64(result.debug.preprocess_set)}
                              alt="Set (preprocessed)"
                              className="extract-verification-debug-img"
                            />
                            <figcaption>Set (preprocessed)</figcaption>
                          </figure>
                        )}
                        {result.debug.preprocess_level && (
                          <figure className="extract-verification-debug-figure">
                            <img
                              src={dataUrlFromBase64(result.debug.preprocess_level)}
                              alt="Level (preprocessed, legacy cyan)"
                              className="extract-verification-debug-img"
                            />
                            <figcaption>Level (preprocessed, legacy cyan)</figcaption>
                          </figure>
                        )}
                        {result.debug.preprocess_stat_crops && result.debug.preprocess_stat_crops.length > 0 && (
                          <figure className="extract-verification-debug-figure">
                            <div className="extract-verification-debug-stat-grid">
                              {result.debug.preprocess_stat_crops.map((b64, i) => (
                                <img
                                  key={i}
                                  src={dataUrlFromBase64(b64)}
                                  alt={`Stat preprocess ${i + 1}`}
                                  className="extract-verification-debug-img extract-verification-debug-stat-cell"
                                />
                              ))}
                            </div>
                            <figcaption>Stat crops (56x56)</figcaption>
                          </figure>
                        )}
                      </div>
                      {(result.debug.ocr_set !== undefined ||
                        result.debug.ocr_level !== undefined ||
                        result.debug.ocr_set_error ||
                        result.debug.ocr_level_error) && (
                        <>
                          <h3 className="extract-verification-debug-heading">OCR output</h3>
                          <div className="extract-verification-debug-ocr">
                            {result.debug.ocr_set_error && (
                              <p className="extract-verification-debug-ocr-line extract-verification-debug-ocr-error" role="alert">
                                <span className="extract-verification-debug-ocr-label">Set OCR error:</span>{' '}
                                {result.debug.ocr_set_error}
                              </p>
                            )}
                            {result.debug.ocr_set !== undefined && (
                              <p className="extract-verification-debug-ocr-line">
                                <span className="extract-verification-debug-ocr-label">Set:</span>{' '}
                                <code className="extract-verification-debug-ocr-value">
                                  {result.debug.ocr_set === '' ? '(empty)' : result.debug.ocr_set}
                                </code>
                              </p>
                            )}
                            {result.debug.ocr_level_error && (
                              <p className="extract-verification-debug-ocr-line extract-verification-debug-ocr-error" role="alert">
                                <span className="extract-verification-debug-ocr-label">Level OCR error:</span>{' '}
                                {result.debug.ocr_level_error}
                              </p>
                            )}
                            {result.debug.ocr_level !== undefined && (
                              <p className="extract-verification-debug-ocr-line">
                                <span className="extract-verification-debug-ocr-label">Level:</span>{' '}
                                <code className="extract-verification-debug-ocr-value">
                                  {result.debug.ocr_level === '' ? '(empty)' : result.debug.ocr_level}
                                </code>
                              </p>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
