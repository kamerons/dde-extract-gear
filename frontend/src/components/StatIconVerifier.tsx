import { useCallback, useEffect, useMemo, useState } from 'react';
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
  VERIFY_TYPE_ORDER,
} from '../lib/statIconLabeling';

function groupItemsByStatType(items: StatIconItem[]): Map<string, StatIconItem[]> {
  const map = new Map<string, StatIconItem[]>();
  for (const item of items) {
    const key = item.stat_type ?? 'unlabeled';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}

export function StatIconVerifier() {
  const [items, setItems] = useState<StatIconItem[]>([]);
  const [statTypes, setStatTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);

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
      setSelectedFilename(null);
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

  const groupsByType = useMemo(() => groupItemsByStatType(items), [items]);

  const orderedTypesWithItems = useMemo(() => {
    return VERIFY_TYPE_ORDER.filter((typeKey) => {
      const group = groupsByType.get(typeKey);
      return group && group.length > 0;
    });
  }, [groupsByType]);

  const applyLabel = useCallback(
    async (statType: string) => {
      if (saving || !selectedFilename) return;
      setSaving(true);
      setError(null);
      try {
        await saveStatIconLabel(selectedFilename, statType);
        setItems((prev) =>
          prev.map((item) =>
            item.filename === selectedFilename ? { ...item, stat_type: statType } : item
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
      const statType = parseHotkeyToStatType(e.key, e.shiftKey, e.ctrlKey, e.altKey);
      if (statType !== null) {
        e.preventDefault();
        e.stopPropagation();
        applyLabel(statType);
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [selectedFilename, saving, applyLabel]);

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
          Run <code>python scripts/produce_stat_icons.py</code> to generate stat icon crops from
          labeled screenshots.
        </p>
      </div>
    );
  }

  return (
    <div className="extract-config-stat-icon-verifier" tabIndex={0}>
      <p className="extract-config-stat-icon-legend" aria-label="Keyboard shortcuts">
        <span>Space = None</span>
        <span>Ctrl+1–4 = Armor</span>
        <span>1–4 = Tower</span>
        <span>Alt+1–6 = Hero</span>
      </p>
      {selectedFilename && (
        <p className="extract-config-stat-icon-progress" role="status">
          Selected: correct with buttons or hotkeys
        </p>
      )}
      <div className="extract-config-stat-icon-verify-sections">
        {orderedTypesWithItems.map((typeKey) => {
          const groupItems = groupsByType.get(typeKey) ?? [];
          const label = statTypeToFriendlyLabel(typeKey);
          return (
            <section
              key={typeKey}
              className="extract-config-stat-icon-verify-section"
              aria-label={`${label}, ${groupItems.length} images`}
            >
              <h4 className="extract-config-stat-icon-verify-section-heading">
                {label} ({groupItems.length})
              </h4>
              <div className="extract-config-stat-icon-verify-row">
                {groupItems.map((item) => (
                  <button
                    key={item.filename}
                    type="button"
                    className={`extract-config-stat-icon-verify-thumb-wrap ${
                      selectedFilename === item.filename
                        ? 'extract-config-stat-icon-verify-thumb-selected'
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
                      src={getStatIconUrl(item.filename)}
                      alt=""
                      className="extract-config-stat-icon-verify-thumb"
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
          <div className="extract-config-stat-icon-image-wrap extract-config-stat-icon-verify-focus">
            <img
              src={getStatIconUrl(selectedFilename)}
              alt="Selected stat icon to correct"
              className="extract-config-stat-icon-image"
            />
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
        </>
      )}
    </div>
  );
}
