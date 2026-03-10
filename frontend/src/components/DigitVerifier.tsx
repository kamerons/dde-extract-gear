import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  listAllDigits,
  getDigitUrl,
  saveDigitLabel,
  type DigitItem,
} from '../api/extract';
import {
  digitLabelToFriendlyLabel,
  getHotkeyForDigitLabel,
  parseHotkeyToDigitLabel,
  BUTTON_GROUPS,
  VERIFY_TYPE_ORDER,
} from '../lib/digitLabeling';

function groupItemsByDigitLabel(items: DigitItem[]): Map<string, DigitItem[]> {
  const map = new Map<string, DigitItem[]>();
  for (const item of items) {
    const key = item.digit_label ?? 'unlabeled';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}

export function DigitVerifier() {
  const [items, setItems] = useState<DigitItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const listRes = await listAllDigits();
      setItems(listRes.items);
      setSelectedFilename(null);
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

  const groupsByLabel = useMemo(() => groupItemsByDigitLabel(items), [items]);

  const orderedLabelsWithItems = useMemo(() => {
    return VERIFY_TYPE_ORDER.filter((labelKey) => {
      const group = groupsByLabel.get(labelKey);
      return group && group.length > 0;
    });
  }, [groupsByLabel]);

  const applyLabel = useCallback(
    async (digitLabel: string) => {
      if (saving || !selectedFilename) return;
      setSaving(true);
      setError(null);
      try {
        await saveDigitLabel(selectedFilename, digitLabel);
        setItems((prev) =>
          prev.map((item) =>
            item.filename === selectedFilename ? { ...item, digit_label: digitLabel } : item
          )
        );
        setSelectedFilename(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to save label');
      } finally {
        setSaving(false);
      }
    },
    [selectedFilename, saving]
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!selectedFilename || saving) return;
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
  }, [selectedFilename, saving, applyLabel]);

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
    <div className="extract-config-digit-verifier" tabIndex={0}>
      <p className="extract-config-stat-icon-legend" aria-label="Keyboard shortcuts">
        <span>0–9 = digit</span>
        <span>Space = Not a digit (artifact)</span>
      </p>
      {selectedFilename && (
        <p className="extract-config-stat-icon-progress" role="status">
          Selected: correct with buttons or hotkeys
        </p>
      )}
      <div className="extract-config-digit-verify-sections">
        {orderedLabelsWithItems.map((labelKey) => {
          const groupItems = groupsByLabel.get(labelKey) ?? [];
          const label = digitLabelToFriendlyLabel(labelKey);
          return (
            <section
              key={labelKey}
              className="extract-config-digit-verify-section"
              aria-label={`${label}, ${groupItems.length} images`}
            >
              <h4 className="extract-config-digit-verify-section-heading">
                {label} ({groupItems.length})
              </h4>
              <div className="extract-config-digit-verify-row">
                {groupItems.map((item) => (
                  <button
                    key={item.filename}
                    type="button"
                    className={`extract-config-digit-verify-thumb-wrap ${
                      selectedFilename === item.filename
                        ? 'extract-config-digit-verify-thumb-selected'
                        : ''
                    }`}
                    onClick={() =>
                      setSelectedFilename((prev) =>
                        prev === item.filename ? null : item.filename
                      )
                    }
                    aria-pressed={selectedFilename === item.filename}
                    aria-label={`${item.filename}, ${label}`}
                  >
                    <img
                      src={getDigitUrl(item.filename)}
                      alt=""
                      className="extract-config-digit-verify-thumb"
                    />
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </div>
      {selectedFilename && (
        <>
          <div className="extract-config-stat-icon-image-wrap extract-config-digit-verify-focus">
            <img
              src={getDigitUrl(selectedFilename)}
              alt="Selected digit to correct"
              className="extract-config-stat-icon-image"
            />
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
                      title={hotkey ? `${digitLabel} [${hotkey}]` : digitLabel}
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
        </>
      )}
    </div>
  );
}
