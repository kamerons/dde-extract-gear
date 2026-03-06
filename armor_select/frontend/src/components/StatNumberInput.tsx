import type { StatType } from '../types';
import { STAT_CATEGORIES, getStatDisplayName } from '../constants';

interface StatNumberInputProps {
  values: Record<StatType, number>;
  onValueChange: (stat: StatType, value: number | undefined) => void;
  label: string;
  description?: string;
  placeholder?: string;
  min?: number;
}

export function StatNumberInput({
  values,
  onValueChange,
  label,
  description,
  placeholder = 'Enter value',
  min = 0,
}: StatNumberInputProps) {
  const handleChange = (stat: StatType, value: string) => {
    const numValue = value === '' ? undefined : Number(value);
    if (numValue !== undefined && (isNaN(numValue) || numValue < min)) {
      return;
    }
    onValueChange(stat, numValue);
  };

  return (
    <div className="stat-number-input">
      <h3 className="stat-section-label">{label}</h3>
      {description && <p className="stat-section-description">{description}</p>}
      <div className="stat-categories">
        {Object.values(STAT_CATEGORIES).map((category) => (
          <div key={category.name} className="stat-category">
            <h4 className="stat-category-name">{category.name}</h4>
            <div className="stat-inputs">
              {category.stats.map((stat) => (
                <label key={stat} className="stat-input-label">
                  <span className="stat-input-name">{getStatDisplayName(stat)}</span>
                  <input
                    type="number"
                    value={values[stat] || ''}
                    onChange={(e) => handleChange(stat, e.target.value)}
                    placeholder={placeholder}
                    min={min}
                    className="stat-number-field"
                  />
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
