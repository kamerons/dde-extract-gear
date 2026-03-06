import { getStatDisplayName } from '../constants';
import type { StatType } from '../types';

interface WasteIndicatorProps {
  wastedPoints: Record<string, number>;
}

export function WasteIndicator({ wastedPoints }: WasteIndicatorProps) {
  const wastedEntries = Object.entries(wastedPoints).filter(([, value]) => value > 0);

  if (wastedEntries.length === 0) {
    return null;
  }

  return (
    <div className="waste-indicator">
      <h4 className="waste-indicator-title">⚠️ Wasted Points (Over Soft Caps)</h4>
      <div className="waste-stats-list">
        {wastedEntries.map(([stat, value]) => (
          <div key={stat} className="waste-stat-item">
            <span className="waste-stat-name">{getStatDisplayName(stat as StatType)}:</span>
            <span className="waste-stat-value">-{Math.round(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
