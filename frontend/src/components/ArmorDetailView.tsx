import { useParams, Link } from 'react-router-dom';
import type { Recommendation } from '../types';
import { RecommendationCard } from './RecommendationCard';

const STORAGE_KEY_PREFIX = 'armor-detail-';

interface StoredArmorDetailPayload {
  recommendation: Recommendation;
  createdAt?: number;
  expiresAt?: number;
}

function isExpired(payload: StoredArmorDetailPayload): boolean {
  return payload.expiresAt != null && Date.now() > payload.expiresAt;
}

function parseStoredPayload(raw: string): StoredArmorDetailPayload | null {
  try {
    return JSON.parse(raw) as StoredArmorDetailPayload;
  } catch {
    return null;
  }
}

function getRecommendationFromStorage(setId: string): Recommendation | null {
  const key = STORAGE_KEY_PREFIX + setId;

  // Prefer durable storage so links survive app/browser restarts.
  try {
    const localRaw = localStorage.getItem(key);
    if (localRaw) {
      const payload = parseStoredPayload(localRaw);
      if (payload?.recommendation) {
        if (isExpired(payload)) {
          localStorage.removeItem(key);
          return null;
        }
        return payload.recommendation;
      }
      // Corrupted or unknown payload format; clean up.
      localStorage.removeItem(key);
      return null;
    }
  } catch {
    // Ignore durable storage access failures and continue with fallback.
  }

  // Backward-compatible fallback for tabs created before localStorage migration.
  try {
    const sessionRaw = sessionStorage.getItem(key);
    if (!sessionRaw) return null;
    return JSON.parse(sessionRaw) as Recommendation;
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
