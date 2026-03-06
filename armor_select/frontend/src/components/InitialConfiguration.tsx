import { useState } from 'react';
import type { StatType, BuildPreferences, Recommendation } from '../types';
import { StatMultiSelect } from './StatMultiSelect';
import { StatNumberInput } from './StatNumberInput';
import { submitInitialPreferences } from '../api/recommendations';

interface InitialConfigurationProps {
  onPreferencesSubmitted: (recommendations: Recommendation[]) => void;
  onLoadingChange?: (isLoading: boolean) => void;
  onError?: (error: string | null) => void;
}

export function InitialConfiguration({
  onPreferencesSubmitted,
  onLoadingChange,
  onError,
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

  const handleSubmit = async () => {
    setIsSubmitting(true);
    onLoadingChange?.(true);
    onError?.(null);

    const preferences: BuildPreferences = {
      maximizeStats,
      ignoreStats,
      minConstraints,
      softCaps,
    };

    try {
      const response = await submitInitialPreferences(preferences);
      onPreferencesSubmitted(response.recommendations);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch recommendations';
      console.error('Error submitting preferences:', error);
      onError?.(errorMessage);
    } finally {
      setIsSubmitting(false);
      onLoadingChange?.(false);
    }
  };

  return (
    <div className="configuration-container">
      <div className="configuration-header">
        <h1>Configure Your Armor Build</h1>
        <p className="header-description">
          Tell us about your build preferences. All fields are optional - configure only what you
          know.
        </p>
      </div>

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

      <div className="configuration-footer">
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
