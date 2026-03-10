import { useCallback, useEffect, useState } from 'react';
import {
  listAllStatIcons,
  getStatIconUrl,
  saveStatIconLabel,
  getStatTypes,
  type StatIconItem,
} from '../api/extract';
import {
  statTypeToFriendlyLabel,
  getHotkeyForStatType,
  parseHotkeyToStatType,
  BUTTON_GROUPS,
} from '../lib/statIconLabeling';

export function StatIconLabeler() {
  const [items, setItems] = useState<StatIconItem[]>([]);
  const [statTypes, setStatTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const currentItem = items[currentIndex] ?? null;
  const currentFilename = currentItem?.filename ?? null;
  const canGoPrevious = items.length > 0 && currentIndex > 0;
  const canGoNext = items.length > 0 && currentIndex < items.length - 1;
  const unlabeledCount = items.filter((i) => i.stat_type === null).length;
  const firstUnlabeledIndex = items.findIndex((i) => i.stat_type === null);
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
      const [listRes, typesRes] = await Promise.all([
        listAllStatIcons(),
        getStatTypes(),
      ]);
      setItems(listRes.items);
      setStatTypes(typesRes.stat_types);
      setCurrentIndex(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setItems([]);
      setStatTypes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const applyLabel = useCallback(
    async (statType: string) => {
      if (saving || !currentFilename) return;
      setSaving(true);
      setError(null);
      try {
        await saveStatIconLabel(currentFilename, statType);
        setItems((prev) =>
          prev.map((item) =>
            item.filename === currentFilename ? { ...item, stat_type: statType } : item
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
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;
      const statType = parseHotkeyToStatType(e.key, e.shiftKey, e.ctrlKey, e.altKey);
      if (statType !== null) {
        e.preventDefault();
        e.stopPropagation();
        applyLabel(statType);
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [currentFilename, saving, applyLabel]);

  if (loading) {
    return <p className="extract-config-coming-soon">Loading stat icons…</p>;
  }

  if (error) {
    return (
      <div className="extract-config-stat-icon-labeler">
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
      <div className="extract-config-stat-icon-labeler">
        <p className="extract-config-coming-soon">No stat icons.</p>
        <p className="stat-section-description">
          Run <code>python scripts/produce_stat_icons.py</code> to generate stat icon crops from labeled screenshots.
        </p>
      </div>
    );
  }

  return (
    <div className="extract-config-stat-icon-labeler" tabIndex={0}>
      <p className="extract-config-stat-icon-legend" aria-label="Keyboard shortcuts">
        <span>Space = None</span>
        <span>Ctrl+1–4 = Armor</span>
        <span>1–4 = Tower</span>
        <span>Alt+1–6 = Hero</span>
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
          src={getStatIconUrl(currentFilename!)}
          alt="Stat icon to label"
          className="extract-config-stat-icon-image"
        />
        {currentItem?.stat_type != null && (
          <p className="extract-config-stat-icon-badge" title="Current label">
            {statTypeToFriendlyLabel(currentItem.stat_type)}
          </p>
        )}
      </div>
      {saving && (
        <p className="extract-config-stat-icon-saving" role="status">
          Saving…
        </p>
      )}
      <div className="extract-config-stat-icon-button-groups">
        {BUTTON_GROUPS.map((group) => {
          const groupStatTypes = group.types.filter((t) => statTypes.includes(t));
          if (groupStatTypes.length === 0) return null;
          return (
            <div key={group.types[0]} className="extract-config-stat-icon-button-row">
              {groupStatTypes.map((statType) => {
                const hotkey = getHotkeyForStatType(statType);
                return (
                  <button
                    key={statType}
                    type="button"
                    className="extract-config-stat-icon-btn"
                    onClick={() => applyLabel(statType)}
                    disabled={saving}
                    title={hotkey ? `${statType} [${hotkey}]` : statType}
                  >
                    <span className="extract-config-stat-icon-btn-label">
                      {statTypeToFriendlyLabel(statType)}
                    </span>
                    {hotkey && (
                      <span className="extract-config-stat-icon-btn-hotkey">[{hotkey}]</span>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
