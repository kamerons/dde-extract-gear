import type { StatType } from '../types';
import { STAT_CATEGORIES, getStatDisplayName } from '../constants';

interface StatMultiSelectProps {
  selectedStats: StatType[];
  onSelectionChange: (stats: StatType[]) => void;
  disabledStats?: StatType[];
  label: string;
  description?: string;
}

export function StatMultiSelect({
  selectedStats,
  onSelectionChange,
  disabledStats = [],
  label,
  description,
}: StatMultiSelectProps) {
  const handleStatToggle = (stat: StatType) => {
    if (disabledStats.includes(stat)) {
      return;
    }

    if (selectedStats.includes(stat)) {
      onSelectionChange(selectedStats.filter((s) => s !== stat));
    } else {
      onSelectionChange([...selectedStats, stat]);
    }
  };

  return (
    <div className="stat-multi-select">
      <h3 className="stat-section-label">{label}</h3>
      {description && <p className="stat-section-description">{description}</p>}
      <div className="stat-categories">
        {Object.values(STAT_CATEGORIES).map((category) => (
          <div key={category.name} className="stat-category">
            <h4 className="stat-category-name">{category.name}</h4>
            <div className="stat-checkboxes">
              {category.stats.map((stat) => {
                const isSelected = selectedStats.includes(stat);
                const isDisabled = disabledStats.includes(stat);
                return (
                  <label
                    key={stat}
                    className={`stat-checkbox-label ${isDisabled ? 'disabled' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={isDisabled}
                      onChange={() => handleStatToggle(stat)}
                    />
                    <span>{getStatDisplayName(stat)}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
