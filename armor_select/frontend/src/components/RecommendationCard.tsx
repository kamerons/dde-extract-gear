import type { Recommendation } from '../types';
import { UpgradePreview } from './UpgradePreview';
import { WasteIndicator } from './WasteIndicator';
import { getStatDisplayName, STAT_CATEGORIES } from '../constants';
import type { StatType } from '../types';

interface RecommendationCardProps {
  recommendation: Recommendation;
  rank: number;
}

function formatScore(score: number): string {
  return (score * 100).toFixed(1);
}

export function RecommendationCard({ recommendation, rank }: RecommendationCardProps) {
  const armorSetName = recommendation.pieces[0]?.armor_set || recommendation.set_id;

  const statsByCategory: Record<string, Array<[string, number]>> = {};

  for (const [stat, value] of Object.entries(recommendation.effective_stats)) {
    if (value === 0) continue;

    const category = Object.entries(STAT_CATEGORIES).find(([, info]) =>
      info.stats.includes(stat as StatType)
    )?.[0] || 'other';

    if (!statsByCategory[category]) {
      statsByCategory[category] = [];
    }

    statsByCategory[category].push([stat, value]);
  }

  return (
    <div className="recommendation-card">
      <div className="recommendation-card-header">
        <div className="recommendation-rank">#{rank}</div>
        <div className="recommendation-title">
          <h2>{armorSetName}</h2>
          <p className="recommendation-set-id">Set ID: {recommendation.set_id}</p>
        </div>
        <div className="recommendation-scores">
          <div className="score-item">
            <span className="score-label">Score</span>
            <span className="score-value">{formatScore(recommendation.score)}</span>
          </div>
          {recommendation.potential_score > 0 && (
            <div className="score-item">
              <span className="score-label">Potential</span>
              <span className="score-value potential">{formatScore(recommendation.potential_score)}</span>
            </div>
          )}
          {recommendation.flexibility_score > 0 && (
            <div className="score-item">
              <span className="score-label">Flexibility</span>
              <span className="score-value flexibility">{formatScore(recommendation.flexibility_score)}</span>
            </div>
          )}
        </div>
      </div>

      <div className="recommendation-card-body">
        <div className="recommendation-pieces">
          <h3>Armor Pieces</h3>
          <div className="pieces-list">
            {recommendation.pieces.map((piece, index) => (
              <div key={index} className="piece-item">
                <span className="piece-type">{piece.armor_type.replace('_', ' ')}</span>
                <span className="piece-level">Level {piece.current_level}/{piece.max_level}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="recommendation-stats">
          <h3>Effective Stats (After Soft Caps)</h3>
          <div className="stats-container">
            {Object.entries(STAT_CATEGORIES).map(([categoryKey, categoryInfo]) => {
              const categoryStats = statsByCategory[categoryKey];
              if (!categoryStats || categoryStats.length === 0) return null;

              return (
                <div key={categoryKey} className="stat-category-section">
                  <h4 className="stat-category-name">{categoryInfo.name}</h4>
                  <div className="stat-list">
                    {categoryStats.map(([stat, value]) => (
                      <div key={stat} className="stat-item">
                        <span className="stat-name">{getStatDisplayName(stat as StatType)}</span>
                        <span className="stat-value">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <UpgradePreview
          currentStats={recommendation.current_stats}
          upgradedStats={recommendation.upgraded_stats}
        />

        <WasteIndicator wastedPoints={recommendation.wasted_points} />
      </div>
    </div>
  );
}
