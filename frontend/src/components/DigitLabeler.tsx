import { useCallback, useEffect, useState } from 'react';
import { listAllDigits, getDigitUrl, saveDigitLabel, type DigitItem } from '../api/extract';
import {
  digitLabelToFriendlyLabel,
  getHotkeyForDigitLabel,
  parseHotkeyToDigitLabel,
  BUTTON_GROUPS,
} from '../lib/digitLabeling';

export function DigitLabeler() {
  const [items, setItems] = useState<DigitItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const currentItem = items[currentIndex] ?? null;
  const currentFilename = currentItem?.filename ?? null;
  const canGoPrevious = items.length > 0 && currentIndex > 0;
  const canGoNext = items.length > 0 && currentIndex < items.length - 1;
  const unlabeledCount = items.filter((i) => i.digit_label === null).length;
  const firstUnlabeledIndex = items.findIndex((i) => i.digit_label === null);
  const canSkipToUnlabeled = firstUnlabeledIndex >= 0 && firstUnlabeledIndex !== currentIndex;

  const goPrevious = useCallback(() => {
    setCurrentIndex((prev) => Math.max(0, prev - 1));
  }, []);
  const goNext = useCallback(() => {
    setCurrentIndex((prev) => Math.min(items.length - 1, prev + 1));
  }, [items.length]);
  const goToFirstUnlabeled = useCallback(() => {
    if (firstUnlabeledIndex >= 0) setCurrentIndex(firstUnlabeledIndex);
  }, [firstUnlabeledIndex]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const listRes = await listAllDigits();
      setItems(listRes.items);
      setCurrentIndex(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const applyLabel = useCallback(
    async (digitLabel: string) => {
      if (saving || !currentFilename) return;
      setSaving(true);
      setError(null);
      try {
        await saveDigitLabel(currentFilename, digitLabel);
        setItems((prev) =>
          prev.map((item) =>
            item.filename === currentFilename ? { ...item, digit_label: digitLabel } : item
          )
        );
        setCurrentIndex((prev) => Math.min(prev + 1, items.length - 1));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to save label');
      } finally {
        setSaving(false);
      }
    },
    [currentFilename, saving, items.length]
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!currentFilename || saving) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
        return;
      const digitLabel = parseHotkeyToDigitLabel(e.key, e.shiftKey, e.ctrlKey, e.altKey);
      if (digitLabel !== null) {
        e.preventDefault();
        e.stopPropagation();
        applyLabel(digitLabel);
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [currentFilename, saving, applyLabel]);

  if (loading) {
    return <p className="extract-config-coming-soon">Loading digits…</p>;
  }

  if (error) {
    return (
      <div className="extract-config-stat-icon-labeler extract-config-digit-labeler">
        <p className="extract-config-stat-icon-error" role="alert">
          {error}
        </p>
        <button type="button" className="extract-config-save-button" onClick={loadData}>
          Retry
        </button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="extract-config-stat-icon-labeler extract-config-digit-labeler">
        <p className="extract-config-coming-soon">No digit images.</p>
        <p className="stat-section-description">
          Run <code>python scripts/produce_stat_digits.py</code> to generate digit crops from
          labeled stat icons.
        </p>
      </div>
    );
  }

  return (
    <div
      className="extract-config-stat-icon-labeler extract-config-digit-labeler"
      tabIndex={0}
      data-digit-labeler
    >
      <p className="extract-config-stat-icon-legend" aria-label="Keyboard shortcuts">
        <span>0–9 = digit</span>
        <span>Space = Not a digit (artifact)</span>
      </p>
      <p className="extract-config-stat-icon-progress" role="status">
        {unlabeledCount} unlabeled · {items.length} total
      </p>
      <div className="extract-config-stat-icon-nav">
        <button
          type="button"
          className="extract-config-stat-icon-nav-btn"
          onClick={goPrevious}
          disabled={!canGoPrevious}
          aria-label="Previous image"
        >
          Previous
        </button>
        <span className="extract-config-stat-icon-nav-index" aria-live="polite">
          {currentIndex + 1} / {items.length}
        </span>
        <button
          type="button"
          className="extract-config-stat-icon-nav-btn"
          onClick={goNext}
          disabled={!canGoNext}
          aria-label="Next image"
        >
          Next
        </button>
        <button
          type="button"
          className="extract-config-stat-icon-nav-btn"
          onClick={goToFirstUnlabeled}
          disabled={!canSkipToUnlabeled}
          aria-label="Skip to first unlabeled image"
          title="Skip to first unlabeled"
        >
          Skip to unlabeled
        </button>
      </div>
      <div className="extract-config-stat-icon-image-wrap">
        <img
          key={currentFilename ?? undefined}
          src={getDigitUrl(currentFilename!)}
          alt="Digit to label"
          className="extract-config-stat-icon-image"
        />
        {currentItem?.digit_label != null && (
          <p className="extract-config-stat-icon-badge" title="Current label">
            {digitLabelToFriendlyLabel(currentItem.digit_label)}
          </p>
        )}
      </div>
      {saving && (
        <p className="extract-config-stat-icon-saving" role="status">
          Saving…
        </p>
      )}
      <div className="extract-config-stat-icon-button-groups">
        {BUTTON_GROUPS.map((group) => (
          <div key={group.types[0]} className="extract-config-stat-icon-button-row">
            {group.types.map((digitLabel) => {
              const hotkey = getHotkeyForDigitLabel(digitLabel);
              return (
                <button
                  key={digitLabel}
                  type="button"
                  className="extract-config-stat-icon-btn"
                  onClick={() => applyLabel(digitLabel)}
                  disabled={saving}
                  title={hotkey ? `${digitLabelToFriendlyLabel(digitLabel)} [${hotkey}]` : digitLabel}
                >
                  <span className="extract-config-stat-icon-btn-label">
                    {digitLabelToFriendlyLabel(digitLabel)}
                  </span>
                  {hotkey && (
                    <span className="extract-config-stat-icon-btn-hotkey">[{hotkey}]</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
