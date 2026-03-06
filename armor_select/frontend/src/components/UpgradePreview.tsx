import { getStatDisplayName, STAT_CATEGORIES } from '../constants';
import type { StatType } from '../types';

interface UpgradePreviewProps {
  currentStats: Record<string, number>;
  upgradedStats: Record<string, number>;
}

function getStatWithLargestImprovement(
  currentStats: Record<string, number>,
  upgradedStats: Record<string, number>
): string | null {
  let largestImprovementStat: string | null = null;
  let largestImprovement = -1;

  for (const [stat, currentValue] of Object.entries(currentStats)) {
    const upgradedValue = upgradedStats[stat] || currentValue;
    const improvement = upgradedValue - currentValue;
    if (improvement > largestImprovement) {
      largestImprovement = improvement;
      largestImprovementStat = stat;
    }
  }

  return largestImprovementStat;
}

export function UpgradePreview({ currentStats, upgradedStats }: UpgradePreviewProps) {
  const allStats = new Set([...Object.keys(currentStats), ...Object.keys(upgradedStats)]);
  const largestImprovementStat = getStatWithLargestImprovement(currentStats, upgradedStats);

  const statsByCategory: Record<string, Array<[string, number, number]>> = {};

  for (const stat of allStats) {
    const currentValue = currentStats[stat] || 0;
    const upgradedValue = upgradedStats[stat] || 0;

    if (currentValue === 0 && upgradedValue === 0) continue;

    const category = Object.entries(STAT_CATEGORIES).find(([, info]) =>
      info.stats.includes(stat as StatType)
    )?.[0] || 'other';

    if (!statsByCategory[category]) {
      statsByCategory[category] = [];
    }

    statsByCategory[category].push([stat, currentValue, upgradedValue]);
  }

  return (
    <div className="upgrade-preview">
      <h4 className="upgrade-preview-title">Upgrade Preview</h4>
      <p className="upgrade-preview-note">
        Upgrading boosts the highest stat on each piece by 10%
      </p>
      <div className="upgrade-stats-container">
        {Object.entries(STAT_CATEGORIES).map(([categoryKey, categoryInfo]) => {
          const categoryStats = statsByCategory[categoryKey];
          if (!categoryStats || categoryStats.length === 0) return null;

          return (
            <div key={categoryKey} className="upgrade-category">
              <h5 className="upgrade-category-name">{categoryInfo.name}</h5>
              <div className="upgrade-stats-list">
                {categoryStats.map(([stat, current, upgraded]) => {
                  const difference = upgraded - current;
                  const isBoosted = stat === largestImprovementStat && difference > 0;

                  return (
                    <div key={stat} className={`upgrade-stat-item ${isBoosted ? 'boosted' : ''}`}>
                      <span className="upgrade-stat-name">{getStatDisplayName(stat as StatType)}</span>
                      <div className="upgrade-stat-values">
                        <span className="upgrade-stat-current">{current}</span>
                        <span className="upgrade-stat-arrow">→</span>
                        <span className="upgrade-stat-upgraded">{upgraded}</span>
                        {difference > 0 && (
                          <span className="upgrade-stat-diff">(+{difference})</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
