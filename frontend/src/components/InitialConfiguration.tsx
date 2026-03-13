import { useCallback, useEffect, useMemo, useState } from 'react';
import type { StatType, BuildPreferences } from '../types';
import { getDataFiles, getRequestFromPreferences } from '../api/recommendations';
import { getStatDisplayName } from '../constants';
import { ALL_STATS } from '../constants';
import { StatMultiSelect } from './StatMultiSelect';
import { StatNumberInput } from './StatNumberInput';

interface InitialConfigurationProps {
  onNavigateToResults: (
    preferences: BuildPreferences,
    dataFile?: string,
    initialWeights?: Record<string, number>
  ) => void;
  onError?: (error: string | null) => void;
  error?: string | null;
}

export function InitialConfiguration({
  onNavigateToResults,
  onError,
  error: configError,
}: InitialConfigurationProps) {
  const [maximizeStats, setMaximizeStats] = useState<StatType[]>([]);
  const [ignoreStats, setIgnoreStats] = useState<StatType[]>([]);
  const [minConstraints, setMinConstraints] = useState<Record<StatType, number>>(
    {} as Record<StatType, number>
  );
  const [softCaps, setSoftCaps] = useState<Record<StatType, number>>(
    {} as Record<StatType, number>
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dataFiles, setDataFiles] = useState<string[]>([]);
  const [selectedDataFile, setSelectedDataFile] = useState<string>('');
  const [localWeights, setLocalWeights] = useState<Record<string, number>>({});

  useEffect(() => {
    getDataFiles()
      .then((files) => {
        setDataFiles(files);
        if (files.length > 0) {
          setSelectedDataFile((prev) => {
            const defaultFile = files.includes('sample.json') ? 'sample.json' : files[0];
            return prev === '' || !files.includes(prev) ? defaultFile : prev;
          });
        }
      })
      .catch(() => setDataFiles([]));
  }, []);

  const derivedWeights = useMemo(() => {
    const preferences: BuildPreferences = {
      maximizeStats,
      ignoreStats,
      minConstraints,
      softCaps,
    };
    return getRequestFromPreferences(preferences).weights;
  }, [maximizeStats, ignoreStats, minConstraints, softCaps]);

  // Sync editable weights when maximize/ignore (or prefs) change so derived values are the default
  useEffect(() => {
    setLocalWeights(derivedWeights);
  }, [derivedWeights]);

  // Validation: can't maximize and ignore the same stat
  const getDisabledStatsForMaximize = (): StatType[] => {
    return ignoreStats;
  };

  const getDisabledStatsForIgnore = (): StatType[] => {
    return maximizeStats;
  };

  const handleMinConstraintChange = (stat: StatType, value: number | undefined) => {
    const newConstraints = { ...minConstraints };
    if (value === undefined) {
      delete newConstraints[stat];
    } else {
      newConstraints[stat] = value;
    }
    setMinConstraints(newConstraints);
  };

  const handleSoftCapChange = (stat: StatType, value: number | undefined) => {
    const newSoftCaps = { ...softCaps };
    if (value === undefined) {
      delete newSoftCaps[stat];
    } else {
      newSoftCaps[stat] = value;
    }
    setSoftCaps(newSoftCaps);
  };

  const handleSubmit = useCallback(() => {
    onError?.(null);

    const preferences: BuildPreferences = {
      maximizeStats,
      ignoreStats,
      minConstraints,
      softCaps,
    };

    setIsSubmitting(true);
    onNavigateToResults(preferences, selectedDataFile || undefined, localWeights);
    setIsSubmitting(false);
  }, [maximizeStats, ignoreStats, minConstraints, softCaps, selectedDataFile, localWeights, onNavigateToResults, onError]);

  return (
    <div className="configuration-container">
      <div className="configuration-header">
        <h1>Configure Your Armor Build</h1>
        <p className="header-description">
          Tell us about your build preferences. All fields are optional - configure only what you
          know.
        </p>
      </div>

      {dataFiles.length > 0 && (
        <div className="configuration-section">
          <h3 className="stat-section-label">Data file</h3>
          <p className="stat-section-description">
            Which collected armor data to use for recommendations (from data/collected/).
          </p>
          <select
            id="data-file-select"
            value={
              dataFiles.includes(selectedDataFile)
                ? selectedDataFile
                : dataFiles.includes('sample.json')
                  ? 'sample.json'
                  : dataFiles[0] ?? ''
            }
            onChange={(e) => setSelectedDataFile(e.target.value)}
            className="configuration-data-file-select"
            aria-label="Select data file"
          >
            {dataFiles.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="configuration-sections">
        <div className="configuration-section">
          <StatMultiSelect
            selectedStats={maximizeStats}
            onSelectionChange={setMaximizeStats}
            disabledStats={getDisabledStatsForMaximize()}
            label="Stats to Maximize"
            description="Select stats you want to prioritize and maximize in your armor set."
          />
        </div>

        <div className="configuration-section">
          <StatMultiSelect
            selectedStats={ignoreStats}
            onSelectionChange={setIgnoreStats}
            disabledStats={getDisabledStatsForIgnore()}
            label="Stats to Ignore"
            description="Select stats you don't care about at all. These won't affect recommendations."
          />
        </div>

        <div className="configuration-section">
          <StatNumberInput
            values={minConstraints}
            onValueChange={handleMinConstraintChange}
            label="Minimum Requirements"
            description="Set minimum values that your armor set must meet. Sets below these values will be filtered out."
            placeholder="Minimum value"
            min={0}
          />
        </div>

        <div className="configuration-section">
          <StatNumberInput
            values={softCaps}
            onValueChange={handleSoftCapChange}
            label="Soft Caps"
            description="Set thresholds where stats become less valuable. Values above the threshold will have diminishing returns."
            placeholder="Threshold value"
            min={0}
          />
        </div>
      </div>

      <div className="configuration-weights-preview">
        <h3 className="config-pane-title">Score weights (preview)</h3>
        <p className="config-formula-description">
          Weights are derived from Stats to Maximize / Ignore; you can edit them below. These
          weights will be used for recommendations.
        </p>
        <div className="config-weights">
          <h4 className="config-section-label">Stat weights (editable)</h4>
          <div className="config-weights-list">
            {ALL_STATS.map((stat) => (
              <label key={stat} className="config-weight-item">
                <span className="config-weight-label">{getStatDisplayName(stat) ?? stat}</span>
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
                  aria-label={`Weight for ${getStatDisplayName(stat) ?? stat}`}
                />
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="configuration-footer">
        {configError && (
          <p className="configuration-error" role="alert">
            {configError}
          </p>
        )}
        <button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="submit-button"
        >
          {isSubmitting ? 'Submitting...' : 'Get Recommendations'}
        </button>
      </div>
    </div>
  );
}
