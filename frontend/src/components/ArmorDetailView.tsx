import { useParams, Link } from 'react-router-dom';
import type { Recommendation } from '../types';
import { RecommendationCard } from './RecommendationCard';

const STORAGE_KEY_PREFIX = 'armor-detail-';

function getRecommendationFromStorage(setId: string): Recommendation | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY_PREFIX + setId);
    if (!raw) return null;
    return JSON.parse(raw) as Recommendation;
  } catch {
    return null;
  }
}

export function ArmorDetailView() {
  const { setId } = useParams<{ setId: string }>();
  const recommendation = setId ? getRecommendationFromStorage(setId) : null;

  if (!setId) {
    return (
      <div className="armor-detail-view armor-detail-view--empty">
        <p>No armor set specified.</p>
        <Link to="/" className="armor-detail-back-link">
          Back to app
        </Link>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="armor-detail-view armor-detail-view--empty">
        <p>Open this armor from the Recommendations results to view details.</p>
        <Link to="/" className="armor-detail-back-link">
          Back to app
        </Link>
      </div>
    );
  }

  return (
    <div className="armor-detail-view">
      <div className="armor-detail-view-header">
        <Link to="/" className="armor-detail-back-link">
          Back to app
        </Link>
      </div>
      <div className="armor-detail-view-content">
        <RecommendationCard
          recommendation={recommendation}
          rank={1}
          variant="detail"
        />
      </div>
    </div>
  );
}
