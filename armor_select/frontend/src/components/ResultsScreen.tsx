import type { Recommendation } from '../types';
import { RecommendationCard } from './RecommendationCard';

interface ResultsScreenProps {
  recommendations: Recommendation[];
  onBack: () => void;
  isLoading?: boolean;
  error?: string | null;
}

export function ResultsScreen({ recommendations, onBack, isLoading, error }: ResultsScreenProps) {
  if (isLoading) {
    return (
      <div className="results-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading recommendations...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="results-container">
        <div className="error-state">
          <h2>Error Loading Recommendations</h2>
          <p>{error}</p>
          <button onClick={onBack} className="back-button">
            Back to Configuration
          </button>
        </div>
      </div>
    );
  }

  if (recommendations.length === 0) {
    return (
      <div className="results-container">
        <div className="empty-state">
          <h2>No Recommendations Found</h2>
          <p>No armor sets match your current preferences. Try adjusting your constraints.</p>
          <button onClick={onBack} className="back-button">
            Back to Configuration
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="results-container">
      <div className="results-header">
        <h1>Armor Recommendations</h1>
        <p className="results-count">Found {recommendations.length} recommendation{recommendations.length !== 1 ? 's' : ''}</p>
        <button onClick={onBack} className="back-button">
          ← Back to Configuration
        </button>
      </div>

      <div className="recommendations-grid">
        {recommendations.map((recommendation, index) => (
          <RecommendationCard key={recommendation.set_id || index} recommendation={recommendation} rank={index + 1} />
        ))}
      </div>
    </div>
  );
}
