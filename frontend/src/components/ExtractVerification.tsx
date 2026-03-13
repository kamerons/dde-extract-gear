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

type SelectedDetail = 'armor_set' | 'level' | string | null;

export function ExtractVerification() {
  const [items, setItems] = useState<VerificationItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statDisplayOrder, setStatDisplayOrder] = useState<string[]>(STAT_DISPLAY_ORDER_DEFAULT);
  const [selectedDetail, setSelectedDetail] = useState<SelectedDetail>(null);
  const [imageFilterPrefix, setImageFilterPrefix] = useState('');

  const filteredItems =
    imageFilterPrefix.trim() === ''
      ? items
      : items.filter((item) => item.filename.startsWith(imageFilterPrefix.trim()));

  const effectiveIndex =
    filteredItems.length > 0
      ? Math.min(currentIndex, filteredItems.length - 1)
      : 0;
  const currentItem = filteredItems.length > 0 ? filteredItems[effectiveIndex] ?? null : null;

  useEffect(() => {
    if (filteredItems.length > 0 && currentIndex >= filteredItems.length) {
      setCurrentIndex(filteredItems.length - 1);
    }
  }, [filteredItems.length, currentIndex]);

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

  useEffect(() => {
    setSelectedDetail(null);
  }, [currentItem?.subdir, currentItem?.filename]);

  const goPrev = useCallback(() => {
    if (filteredItems.length === 0) return;
    setCurrentIndex((i) => (i <= 0 ? filteredItems.length - 1 : i - 1));
  }, [filteredItems.length]);

  const goNext = useCallback(() => {
    if (filteredItems.length === 0) return;
    setCurrentIndex((i) => (i >= filteredItems.length - 1 ? 0 : i + 1));
  }, [filteredItems.length]);

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
            <label className="extract-verification-filter">
              <span className="extract-verification-filter-label">Prefix:</span>
              <input
                type="text"
                className="extract-verification-filter-input"
                value={imageFilterPrefix}
                onChange={(e) => setImageFilterPrefix(e.target.value)}
                placeholder="e.g. run1"
                aria-label="Filter images by filename prefix"
              />
            </label>
            <button
              type="button"
              onClick={goPrev}
              disabled={loading || filteredItems.length === 0}
              aria-label="Previous screenshot"
            >
              Previous
            </button>
            <span className="extract-verification-counter">
              {filteredItems.length > 0 ? `${effectiveIndex + 1} / ${filteredItems.length}` : '0 / 0'}
            </span>
            <select
              className="extract-verification-jump"
              value={filteredItems.length > 0 ? effectiveIndex : ''}
              onChange={(e) => setCurrentIndex(Number(e.target.value))}
              disabled={loading || filteredItems.length === 0}
              aria-label="Jump to image"
            >
              {filteredItems.length === 0 ? (
                <option value="">No images match</option>
              ) : (
                filteredItems.map((item, i) => (
                  <option key={`${item.subdir}-${item.filename}`} value={i}>
                    {item.subdir.split('/').pop()} / {item.filename}
                  </option>
                ))
              )}
            </select>
            <button
              type="button"
              onClick={goNext}
              disabled={loading || filteredItems.length === 0}
              aria-label="Next screenshot"
            >
              Next
            </button>
          </div>
          <div className="extract-verification-layout">
            <div className="extract-verification-left">
              {loading && <p className="extract-verification-loading">Verifying…</p>}
              {!loading && error && currentItem && (
                <p className="extract-verification-error" role="alert">
                  {error}
                </p>
              )}
              {!loading && result && (
                <>
                  <div className="extract-verification-left-top">
                    <div className="extract-verification-stats-card">
                      {result.error && (
                        <p className="extract-verification-partial-error" role="alert">
                          {result.error}
                        </p>
                      )}
                      <dl className="extract-verification-dl">
                        <div
                          className={`extract-verification-dl-term${selectedDetail === 'armor_set' ? ' extract-verification-dl-term--selected' : ''}`}
                          onClick={() => setSelectedDetail('armor_set')}
                          onKeyDown={(e) => e.key === 'Enter' && setSelectedDetail('armor_set')}
                          role="button"
                          tabIndex={0}
                          aria-pressed={selectedDetail === 'armor_set'}
                        >
                          <dt>Armor set</dt>
                          <dd>{result.armor_set ?? '\u2014'}</dd>
                        </div>
                        <div
                          className={`extract-verification-dl-term${selectedDetail === 'level' ? ' extract-verification-dl-term--selected' : ''}`}
                          onClick={() => setSelectedDetail('level')}
                          onKeyDown={(e) => e.key === 'Enter' && setSelectedDetail('level')}
                          role="button"
                          tabIndex={0}
                          aria-pressed={selectedDetail === 'level'}
                        >
                          <dt>Level</dt>
                          <dd>
                            {result.current_level != null && result.max_level != null
                              ? `${result.current_level} / ${result.max_level}`
                              : result.current_level != null
                                ? String(result.current_level)
                                : '\u2014'}
                          </dd>
                        </div>
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
                                  <tr
                                    key={name}
                                    className={selectedDetail === name ? 'extract-verification-stat-row--selected' : ''}
                                    onClick={() => setSelectedDetail(name)}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => e.key === 'Enter' && setSelectedDetail(name)}
                                    aria-pressed={selectedDetail === name}
                                  >
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
                    </div>
                    <div className="extract-verification-debug-panel">
                      {selectedDetail == null && (
                        <p className="extract-verification-debug-panel-empty">
                          Click a stat or region to see debug info.
                        </p>
                      )}
                      {selectedDetail === 'armor_set' && result.debug && (
                        <>
                          <h3 className="extract-verification-debug-heading">Region used</h3>
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
                          </div>
                          <h3 className="extract-verification-debug-heading">Preprocessed</h3>
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
                          </div>
                          <h3 className="extract-verification-debug-heading">Set (OCR)</h3>
                          <div className="extract-verification-debug-ocr">
                            {result.debug.ocr_set_error && (
                              <p className="extract-verification-debug-ocr-line extract-verification-debug-ocr-error" role="alert">
                                <span className="extract-verification-debug-ocr-label">OCR error:</span>{' '}
                                {result.debug.ocr_set_error}
                              </p>
                            )}
                            {result.debug.ocr_set !== undefined && (
                              <p className="extract-verification-debug-ocr-line">
                                <span className="extract-verification-debug-ocr-label">OCR:</span>{' '}
                                <code className="extract-verification-debug-ocr-value">
                                  {result.debug.ocr_set === '' ? '(empty)' : result.debug.ocr_set}
                                </code>
                              </p>
                            )}
                          </div>
                        </>
                      )}
                      {selectedDetail === 'level' && result.debug && (
                        <>
                          <h3 className="extract-verification-debug-heading">Region used</h3>
                          <div className="extract-verification-debug-regions">
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
                          </div>
                          <h3 className="extract-verification-debug-heading">Preprocessed</h3>
                          <div className="extract-verification-debug-preprocess">
                            {result.debug.preprocess_level && (
                              <figure className="extract-verification-debug-figure">
                                <img
                                  src={dataUrlFromBase64(result.debug.preprocess_level)}
                                  alt="Level (preprocessed)"
                                  className="extract-verification-debug-img"
                                />
                                <figcaption>Level (preprocessed)</figcaption>
                              </figure>
                            )}
                          </div>
                          <h3 className="extract-verification-debug-heading">Level info</h3>
                          <div className="extract-verification-debug-ocr">
                            {result.debug.level_via_digit !== undefined && (
                              <p className="extract-verification-debug-ocr-line">
                                <span className="extract-verification-debug-ocr-label">Source:</span>{' '}
                                {result.debug.level_via_digit
                                  ? 'digit detector (clusters + model)'
                                  : 'OCR fallback'}
                              </p>
                            )}
                            <p className="extract-verification-debug-ocr-line">
                              <span className="extract-verification-debug-ocr-label">Parsed level:</span>{' '}
                              {result.current_level != null && result.max_level != null
                                ? `${result.current_level} / ${result.max_level}`
                                : result.current_level != null
                                  ? String(result.current_level)
                                  : '(none)'}
                            </p>
                            {result.debug.ocr_level_error && (
                              <p className="extract-verification-debug-ocr-line extract-verification-debug-ocr-error" role="alert">
                                <span className="extract-verification-debug-ocr-label">Level OCR error:</span>{' '}
                                {result.debug.ocr_level_error}
                              </p>
                            )}
                            {result.debug.ocr_level !== undefined && !result.debug.level_via_digit && (
                              <p className="extract-verification-debug-ocr-line">
                                <span className="extract-verification-debug-ocr-label">Level OCR text:</span>{' '}
                                <code className="extract-verification-debug-ocr-value">
                                  {result.debug.ocr_level === '' ? '(empty)' : result.debug.ocr_level}
                                </code>
                              </p>
                            )}
                          </div>
                        </>
                      )}
                      {selectedDetail !== null &&
                        selectedDetail !== 'armor_set' &&
                        selectedDetail !== 'level' &&
                        (result.debug?.stat_debug?.[selectedDetail] ? (
                          <>
                            <h3 className="extract-verification-debug-heading">Region used</h3>
                            <figure className="extract-verification-debug-figure">
                              <img
                                src={dataUrlFromBase64(result.debug.stat_debug[selectedDetail].region)}
                                alt={`${selectedDetail} region`}
                                className="extract-verification-debug-img"
                              />
                              <figcaption>{selectedDetail} (raw)</figcaption>
                            </figure>
                            <h3 className="extract-verification-debug-heading">Preprocessed (56x56)</h3>
                            <figure className="extract-verification-debug-figure">
                              <img
                                src={dataUrlFromBase64(result.debug.stat_debug[selectedDetail].preprocess)}
                                alt={`${selectedDetail} preprocessed`}
                                className="extract-verification-debug-img"
                              />
                              <figcaption>{selectedDetail} (56x56)</figcaption>
                            </figure>
                            <p className="extract-verification-debug-ocr-line">
                              <span className="extract-verification-debug-ocr-label">Value:</span>{' '}
                              {result.stats[selectedDetail] !== undefined ? result.stats[selectedDetail] : '\u2014'}
                            </p>
                            <h3 className="extract-verification-debug-heading">Digit crops</h3>
                            <div className="extract-verification-debug-digit-crops">
                              {result.debug.stat_debug[selectedDetail].digit_crops.map((b64, i) => (
                                <img
                                  key={i}
                                  src={dataUrlFromBase64(b64)}
                                  alt={`Digit ${i + 1}`}
                                />
                              ))}
                              {result.debug.stat_debug[selectedDetail].digit_crops.length === 0 && (
                                <span className="extract-verification-debug-panel-empty">No digits extracted</span>
                              )}
                            </div>
                          </>
                        ) : (
                          <p className="extract-verification-debug-panel-empty">
                            No debug images for this stat.
                          </p>
                        ))}
                    </div>
                  </div>
                  {result.debug && (
                    <div className="extract-verification-regions-strip">
                      {result.debug.region_card && (
                        <button
                          type="button"
                          className={`extract-verification-region-thumb${selectedDetail === null ? ' extract-verification-region-thumb--selected' : ''}`}
                          onClick={() => setSelectedDetail(null)}
                          aria-label="Card crop"
                          aria-pressed={selectedDetail === null}
                          title="Card"
                        >
                          <img src={dataUrlFromBase64(result.debug.region_card)} alt="" />
                          <span className="extract-verification-region-thumb-caption">Card</span>
                        </button>
                      )}
                      {result.debug.region_set && (
                        <button
                          type="button"
                          className={`extract-verification-region-thumb${selectedDetail === 'armor_set' ? ' extract-verification-region-thumb--selected' : ''}`}
                          onClick={() => setSelectedDetail('armor_set')}
                          aria-label="Set region"
                          aria-pressed={selectedDetail === 'armor_set'}
                          title="Armor set"
                        >
                          <img src={dataUrlFromBase64(result.debug.region_set)} alt="" />
                          <span className="extract-verification-region-thumb-caption">Set</span>
                        </button>
                      )}
                      {result.debug.region_level && (
                        <button
                          type="button"
                          className={`extract-verification-region-thumb${selectedDetail === 'level' ? ' extract-verification-region-thumb--selected' : ''}`}
                          onClick={() => setSelectedDetail('level')}
                          aria-label="Level region"
                          aria-pressed={selectedDetail === 'level'}
                          title="Level"
                        >
                          <img src={dataUrlFromBase64(result.debug.region_level)} alt="" />
                          <span className="extract-verification-region-thumb-caption">Level</span>
                        </button>
                      )}
                      {result.debug.stat_debug &&
                        [
                          ...statDisplayOrder.filter((name) => result.debug?.stat_debug?.[name]),
                          ...Object.keys(result.debug.stat_debug).filter(
                            (name) => !statDisplayOrder.includes(name)
                          ),
                        ].map((name) => (
                          <button
                            key={name}
                            type="button"
                            className={`extract-verification-region-thumb${selectedDetail === name ? ' extract-verification-region-thumb--selected' : ''}`}
                            onClick={() => setSelectedDetail(name)}
                            aria-label={`Stat ${name}`}
                            aria-pressed={selectedDetail === name}
                            title={name}
                          >
                            <img
                              src={dataUrlFromBase64(result.debug!.stat_debug![name].region)}
                              alt=""
                            />
                            <span className="extract-verification-region-thumb-caption">{name}</span>
                          </button>
                        ))}
                    </div>
                  )}
                </>
              )}
            </div>
            <div className="extract-verification-image-wrap">
              {currentItem && (
                <>
                  <img
                    src={
                      result?.debug?.region_card
                        ? dataUrlFromBase64(result.debug.region_card)
                        : getScreenshotUrl(currentItem.filename, currentItem.subdir, { crop: true })
                    }
                    alt="Card crop"
                    className="extract-verification-image"
                  />
                  <p className="extract-verification-caption">
                    {currentItem.subdir.split('/').pop()} / {currentItem.filename}
                  </p>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
