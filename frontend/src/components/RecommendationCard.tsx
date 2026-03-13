import { useState } from 'react';
import type { Recommendation, RecommendationPiece } from '../types';
import { WasteIndicator } from './WasteIndicator';
import { getStatDisplayName, STAT_CATEGORIES } from '../constants';
import type { StatType } from '../types';

interface RecommendationCardProps {
  recommendation: Recommendation;
  rank: number;
  onCompareWith?: () => void;
  isCompareSelected?: boolean;
  originalScore?: number;
  originalRank?: number;
}

function formatScore(score: number): string {
  return (score * 100).toFixed(1);
}

function PieceLocation({ piece }: { piece: RecommendationPiece }) {
  const hasLocation = piece.filename != null || piece.row != null || piece.col != null;
  if (!hasLocation) return null;
  return (
    <div className="piece-location">
      {piece.filename != null && (
        <span className="piece-filename" title={piece.subdir ? `${piece.subdir}/${piece.filename}` : piece.filename}>
          {piece.filename}
        </span>
      )}
      {piece.row != null && piece.col != null && (
        <span className="piece-row-col">
          Row {piece.row}, Col {piece.col}
          <span className="piece-row-col-hint"> (within this armor type)</span>
        </span>
      )}
    </div>
  );
}

export function RecommendationCard({
  recommendation,
  rank,
  onCompareWith,
  isCompareSelected,
  originalScore,
  originalRank,
}: RecommendationCardProps) {
  const [expandedPieceIndex, setExpandedPieceIndex] = useState<number | null>(null);
  const [armorPiecesExpanded, setArmorPiecesExpanded] = useState(false);
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
        {onCompareWith != null && (
          <button
            type="button"
            className={`compare-with-button ${isCompareSelected ? 'compare-with-selected' : ''}`}
            onClick={onCompareWith}
            aria-pressed={isCompareSelected}
          >
            Compare with
          </button>
        )}
        <div className="recommendation-scores">
          <div className="score-item">
            <span className="score-label">Score</span>
            <span className="score-value-row">
              <span className="score-value">
                {formatScore(originalScore != null ? originalScore : recommendation.score)}
              </span>
              {originalScore != null && originalScore !== recommendation.score && (
                <span
                  className={`score-delta ${recommendation.score > originalScore ? 'improved' : 'worse'}`}
                  aria-label={`Updated: ${formatScore(recommendation.score)}`}
                >
                  {' \u2192 '}
                  {formatScore(recommendation.score)}
                </span>
              )}
            </span>
          </div>
          {originalRank != null && (
            <div className="score-item rank-item">
              <span className="score-label">Rank</span>
              <span className="score-value-row">
                <span className="score-value">#{originalRank}</span>
                {originalRank !== rank && (
                  <span
                    className={`score-delta ${rank < originalRank ? 'improved' : 'worse'}`}
                    aria-label={`Updated: #${rank}`}
                  >
                    {' \u2192 '}#{rank}
                  </span>
                )}
              </span>
            </div>
          )}
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
          <button
            type="button"
            className="recommendation-pieces-toggle"
            onClick={() => setArmorPiecesExpanded((v) => !v)}
            aria-expanded={armorPiecesExpanded}
            aria-controls={`armor-pieces-list-${rank}`}
            id={`armor-pieces-toggle-${rank}`}
          >
            <span className="recommendation-pieces-toggle-icon" aria-hidden>
              {armorPiecesExpanded ? '\u25BC' : '\u25B6'}
            </span>
            <h3>Armor Pieces</h3>
          </button>
          {armorPiecesExpanded && (
          <div
            id={`armor-pieces-list-${rank}`}
            className="pieces-list"
            role="region"
            aria-labelledby={`armor-pieces-toggle-${rank}`}
          >
            {recommendation.pieces.map((piece, index) => (
              <div key={index} className="piece-item">
                <button
                  type="button"
                  className="piece-item-button"
                  onClick={() => setExpandedPieceIndex((i) => (i === index ? null : index))}
                  aria-expanded={expandedPieceIndex === index}
                  aria-controls={`piece-details-${rank}-${index}`}
                  id={`piece-button-${rank}-${index}`}
                >
                  <span className="piece-type">{piece.armor_type.replace(/_/g, ' ')}</span>
                  <span className="piece-level">Level {piece.current_level}/{piece.max_level}</span>
                  <PieceLocation piece={piece} />
                </button>
                {expandedPieceIndex === index && (
                  <div
                    id={`piece-details-${rank}-${index}`}
                    className="piece-details"
                    role="region"
                    aria-labelledby={`piece-button-${rank}-${index}`}
                  >
                    <div className="piece-details-meta">
                      {piece.filename != null && (
                        <div className="piece-details-row">
                          <span className="piece-details-label">File</span>
                          <span className="piece-details-value">
                            {piece.subdir ? `${piece.subdir}/` : ''}{piece.filename}
                          </span>
                          <button
                            type="button"
                            className="piece-copy-button"
                            onClick={(e) => {
                              e.stopPropagation();
                              const path = piece.subdir ? `${piece.subdir}/${piece.filename}` : piece.filename ?? '';
                              void navigator.clipboard.writeText(path);
                            }}
                          >
                            Copy path
                          </button>
                        </div>
                      )}
                      {piece.page != null && (
                        <div className="piece-details-row">
                          <span className="piece-details-label">Page</span>
                          <span className="piece-details-value">{piece.page}</span>
                        </div>
                      )}
                      {piece.row != null && piece.col != null && (
                        <div className="piece-details-row">
                          <span className="piece-details-label">Position (within this armor type)</span>
                          <span className="piece-details-value">Row {piece.row}, Col {piece.col}</span>
                        </div>
                      )}
                      <div className="piece-details-row">
                        <span className="piece-details-label">Set</span>
                        <span className="piece-details-value">{piece.armor_set}</span>
                      </div>
                      <div className="piece-details-row">
                        <span className="piece-details-label">Level</span>
                        <span className="piece-details-value">{piece.current_level} / {piece.max_level}</span>
                      </div>
                    </div>
                    <div className="piece-details-stats">
                      <h4 className="piece-details-stats-title">Stats</h4>
                      <div className="piece-details-stat-list">
                        {Object.entries(piece.stats)
                          .filter(([, v]) => v !== 0)
                          .map(([stat, value]) => (
                            <div key={stat} className="piece-details-stat-item">
                              <span className="stat-name">{getStatDisplayName(stat as StatType) ?? stat}</span>
                              <span className="stat-value">{value}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          )}
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
                        <span className="stat-name">{getStatDisplayName(stat as StatType) ?? stat}</span>
                        <span className="stat-value">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {recommendation.score_breakdown &&
          Object.keys(recommendation.score_breakdown).length > 0 && (
            <div className="recommendation-score-breakdown">
              <h3>Score breakdown</h3>
              <div className="score-breakdown-list">
                {Object.entries(recommendation.score_breakdown)
                  .filter(([, contribution]) => contribution !== 0)
                  .sort(([, a], [, b]) => b - a)
                  .map(([stat, contribution]) => (
                    <div key={stat} className="score-breakdown-item">
                      <span className="stat-name">{getStatDisplayName(stat as StatType) ?? stat}</span>
                      <span className="score-value">{formatScore(contribution)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}

        <WasteIndicator wastedPoints={recommendation.wasted_points} />
      </div>
    </div>
  );
}
