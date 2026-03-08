import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getLatestPreview,
  getScreenshotUrl,
  fetchBoxes,
  type TrainingPreviewItem,
  type TrainingPreviewResponse,
  type ExtractBox,
  type ImageType,
} from '../api/extract';

/** 25% of natural size so preview fits in sidebar */
const PREVIEW_DISPLAY_SCALE = 0.25;

function subdirToImageType(subdir: string): ImageType {
  return subdir.includes('blueprint') ? 'blueprint' : 'regular';
}

const PREVIEW_POLL_INTERVAL_MS = 2500;

export interface TrainingPreviewProps {
  /** When set (e.g. from task status poll), preview is synced with training spinner and shows immediately. */
  latestPreview?: TrainingPreviewResponse | null;
  /** When set (e.g. loaded model results), use this as the only data source and do not poll. */
  fixedPreview?: TrainingPreviewResponse | null;
  /** When true and fixedPreview is used, show loading state instead of empty message. */
  fixedPreviewLoading?: boolean;
}

export function TrainingPreview({ latestPreview, fixedPreview, fixedPreviewLoading }: TrainingPreviewProps) {
  const [items, setItems] = useState<TrainingPreviewItem[]>([]);
  const [scaleRegular, setScaleRegular] = useState<number>(1.0);
  const [scaleBlueprint, setScaleBlueprint] = useState<number>(1.0);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(!fixedPreview);
  const [error, setError] = useState<string | null>(null);
  const [boxesGt, setBoxesGt] = useState<ExtractBox[]>([]);
  const [boxesPred, setBoxesPred] = useState<ExtractBox[]>([]);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollLatest = useCallback(() => {
    getLatestPreview()
      .then((preview) => {
        if (preview && preview.items.length > 0) {
          setItems(preview.items);
          setScaleRegular(preview.scale_regular);
          setScaleBlueprint(preview.scale_blueprint);
          setError(null);
          setIndex((i) => (i >= preview.items.length ? 0 : i));
        } else {
          setItems((prev) => (prev.length > 0 ? prev : []));
        }
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed to load preview');
        setItems([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (fixedPreview != null) {
      setLoading(false);
      return;
    }
    pollLatest();
    pollRef.current = setInterval(pollLatest, PREVIEW_POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [fixedPreview, pollLatest]);

  useEffect(() => {
    if (fixedPreview?.items?.length) {
      setItems(fixedPreview.items);
      setScaleRegular(fixedPreview.scale_regular);
      setScaleBlueprint(fixedPreview.scale_blueprint);
      setError(null);
      setIndex(0);
    }
  }, [fixedPreview]);

  useEffect(() => {
    if (fixedPreview != null) return;
    if (latestPreview?.items?.length) {
      setItems(latestPreview.items);
      setScaleRegular(latestPreview.scale_regular);
      setScaleBlueprint(latestPreview.scale_blueprint);
      setError(null);
      setIndex((i) => (i >= latestPreview.items.length ? 0 : i));
    }
  }, [fixedPreview, latestPreview]);

  const fromProp = fixedPreview?.items?.length
    ? fixedPreview
    : latestPreview?.items?.length
      ? latestPreview
      : null;
  const displayItems = fromProp?.items ?? items;
  const displayScaleRegular = fromProp ? fromProp.scale_regular : scaleRegular;
  const displayScaleBlueprint = fromProp ? fromProp.scale_blueprint : scaleBlueprint;

  const safeIndex = displayItems.length > 0 ? Math.min(index, displayItems.length - 1) : 0;
  const item = displayItems[safeIndex] ?? null;
  const imageType = item ? subdirToImageType(item.subdir) : 'regular';
  const scale = imageType === 'blueprint' ? displayScaleBlueprint : displayScaleRegular;

  // Reset image state when switching to another item (use index so augments of same source reset)
  useEffect(() => {
    setImageSize(null);
    setImageError(null);
  }, [safeIndex, item?.filename, item?.subdir, item?.augment_index]);

  // Use backend-provided boxes when present; otherwise fall back to fetchBoxes (e.g. old cached previews).
  useEffect(() => {
    if (!item) {
      setBoxesGt([]);
      setBoxesPred([]);
      return;
    }
    if (item.boxes_gt != null && item.boxes_pred != null) {
      setBoxesGt(item.boxes_gt);
      setBoxesPred(item.boxes_pred);
      return;
    }
    let cancelled = false;
    Promise.all([
      fetchBoxes(item.origin_x, item.origin_y, scale, imageType),
      fetchBoxes(item.pred_x, item.pred_y, scale, imageType),
    ])
      .then(([resGt, resPred]) => {
        if (!cancelled) {
          setBoxesGt(resGt.boxes);
          setBoxesPred(resPred.boxes);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBoxesGt([]);
          setBoxesPred([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [item, scale, imageType]);

  const handlePrev = useCallback(() => {
    setIndex((i) => (i <= 0 ? displayItems.length - 1 : i - 1));
  }, [displayItems.length]);

  const handleNext = useCallback(() => {
    setIndex((i) => (i >= displayItems.length - 1 ? 0 : i + 1));
  }, [displayItems.length]);

  useEffect(() => {
    if (displayItems.length > 0 && index >= displayItems.length) {
      setIndex(0);
    }
  }, [displayItems.length, index]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (displayItems.length === 0) return;
      if (e.key === 'ArrowLeft') {
        handlePrev();
        e.preventDefault();
      } else if (e.key === 'ArrowRight') {
        handleNext();
        e.preventDefault();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [displayItems.length, handlePrev, handleNext]);

  const showLoading = (loading && displayItems.length === 0) || (fixedPreview != null && fixedPreviewLoading);
  if (showLoading) {
    return (
      <div className="extract-config-training-preview">
        <p className="extract-config-preview-loading">Loading preview…</p>
      </div>
    );
  }

  if (error || displayItems.length === 0) {
    return (
      <div className="extract-config-training-preview">
        <p className="extract-config-preview-empty" style={{ whiteSpace: 'pre-wrap' }}>
          {error ?? (fixedPreview != null ? 'No results for this model.' : 'Run training to see preview.')}
        </p>
      </div>
    );
  }

  const displayWidth = imageSize ? imageSize.width * PREVIEW_DISPLAY_SCALE : 0;
  const displayHeight = imageSize ? imageSize.height * PREVIEW_DISPLAY_SCALE : 0;

  return (
    <div className="extract-config-training-preview">
      <div className="extract-config-preview-nav">
        <button
          type="button"
          className="extract-config-preview-btn"
          onClick={handlePrev}
          aria-label="Previous image"
        >
          Previous
        </button>
        <span className="extract-config-preview-index">
          {safeIndex + 1} / {displayItems.length}
          {item?.augment_index != null && (
            <span className="extract-config-preview-index-augment">
              {' '}({item.filename} · augment {item.augment_index})
            </span>
          )}
        </span>
        <button
          type="button"
          className="extract-config-preview-btn"
          onClick={handleNext}
          aria-label="Next image"
        >
          Next
        </button>
      </div>
      <div
        className="extract-config-preview-image-wrap"
        style={{
          width: displayWidth || 'auto',
          height: displayHeight || 'auto',
          minHeight: 120,
        }}
      >
        {imageError && (
          <p className="extract-config-preview-empty" style={{ padding: '0.5rem' }}>
            {imageError}
          </p>
        )}
        <img
          src={item.image_data_url ?? getScreenshotUrl(item.filename, item.subdir, { crop: true })}
          alt={item.augment_index != null ? `Test sample ${safeIndex + 1} (augment ${item.augment_index})` : `Test sample ${safeIndex + 1}`}
          className="extract-config-preview-image"
          style={{
            width: displayWidth || undefined,
            height: displayHeight || undefined,
            display: imageError ? 'none' : undefined,
          }}
          onLoad={(e) => {
            setImageError(null);
            const img = e.currentTarget;
            setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
          }}
          onError={() => {
            setImageError('Screenshot failed to load. Check API base URL (e.g. VITE_API_BASE_URL) if using Docker.');
          }}
          draggable={false}
        />
        {imageSize && (
          <>
            <svg
              className="extract-config-preview-overlay extract-config-preview-overlay-gt"
              width={displayWidth}
              height={displayHeight}
              style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
            >
              {boxesGt.map((b, i) => (
                <rect
                  key={i}
                  x={b.x * PREVIEW_DISPLAY_SCALE}
                  y={b.y * PREVIEW_DISPLAY_SCALE}
                  width={b.width * PREVIEW_DISPLAY_SCALE}
                  height={b.height * PREVIEW_DISPLAY_SCALE}
                  fill="none"
                  stroke="#0a0"
                  strokeWidth={1.5}
                />
              ))}
            </svg>
            <svg
              className="extract-config-preview-overlay extract-config-preview-overlay-pred"
              width={displayWidth}
              height={displayHeight}
              style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
            >
              {boxesPred.map((b, i) => (
                <rect
                  key={i}
                  x={b.x * PREVIEW_DISPLAY_SCALE}
                  y={b.y * PREVIEW_DISPLAY_SCALE}
                  width={b.width * PREVIEW_DISPLAY_SCALE}
                  height={b.height * PREVIEW_DISPLAY_SCALE}
                  fill="none"
                  stroke="#06c"
                  strokeWidth={1.5}
                />
              ))}
            </svg>
          </>
        )}
      </div>
    </div>
  );
}
