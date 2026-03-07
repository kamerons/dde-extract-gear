import { useCallback, useEffect, useRef, useState } from 'react';
import {
  startPreviewTask,
  getTrainingTaskStatus,
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

const PREVIEW_POLL_INTERVAL_MS = 1500;

export function TrainingPreview() {
  const [items, setItems] = useState<TrainingPreviewItem[]>([]);
  const [scaleRegular, setScaleRegular] = useState<number>(1.0);
  const [scaleBlueprint, setScaleBlueprint] = useState<number>(1.0);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modelFormat, setModelFormat] = useState<string | null>(null);
  const [boxesGt, setBoxesGt] = useState<ExtractBox[]>([]);
  const [boxesPred, setBoxesPred] = useState<ExtractBox[]>([]);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError(null);
    setModelFormat(null);
    try {
      const { task_id } = await startPreviewTask();
      const poll = () => {
        getTrainingTaskStatus(task_id).then((status) => {
          if (status.status === 'completed' && status.results) {
            const res = status.results as TrainingPreviewResponse;
            if (res.items && Array.isArray(res.items)) {
              setItems(res.items);
              setScaleRegular(Number(res.scale_regular) || 1.0);
              setScaleBlueprint(Number(res.scale_blueprint) || 1.0);
              setIndex(0);
            }
            if (status.model_format) {
              setModelFormat(status.model_format === 'keras' ? '.keras' : 'HDF5');
            }
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setLoading(false);
          } else if (status.status === 'failed' || status.status === 'cancelled') {
            setError(status.error ?? (status.status === 'failed' ? 'Preview failed' : 'Cancelled'));
            setItems([]);
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setLoading(false);
          }
        }).catch((e) => {
          setError(e instanceof Error ? e.message : 'Failed to get preview status');
          setItems([]);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setLoading(false);
        });
      };
      poll();
      pollRef.current = setInterval(poll, PREVIEW_POLL_INTERVAL_MS);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load preview');
      setItems([]);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPreview();
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, [loadPreview]);

  const item = items[index] ?? null;
  const imageType = item ? subdirToImageType(item.subdir) : 'regular';
  const scale = imageType === 'blueprint' ? scaleBlueprint : scaleRegular;

  // Reset image state when switching to another item
  useEffect(() => {
    setImageSize(null);
    setImageError(null);
  }, [item?.filename, item?.subdir]);

  useEffect(() => {
    if (!item) {
      setBoxesGt([]);
      setBoxesPred([]);
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
    setIndex((i) => (i <= 0 ? items.length - 1 : i - 1));
  }, [items.length]);

  const handleNext = useCallback(() => {
    setIndex((i) => (i >= items.length - 1 ? 0 : i + 1));
  }, [items.length]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (items.length === 0) return;
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
  }, [items.length, handlePrev, handleNext]);

  if (loading) {
    return (
      <div className="extract-config-training-preview">
        <p className="extract-config-preview-loading">Loading preview…</p>
      </div>
    );
  }

  if (error || items.length === 0) {
    return (
      <div className="extract-config-training-preview">
        <p className="extract-config-preview-empty" style={{ whiteSpace: 'pre-wrap' }}>
          {error ?? 'No test set or no model. Run training first.'}
        </p>
      </div>
    );
  }

  const displayWidth = imageSize ? imageSize.width * PREVIEW_DISPLAY_SCALE : 0;
  const displayHeight = imageSize ? imageSize.height * PREVIEW_DISPLAY_SCALE : 0;

  return (
    <div className="extract-config-training-preview">
      {modelFormat != null && (
        <p className="extract-config-preview-format" role="status">
          Model format: {modelFormat}
        </p>
      )}
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
          {index + 1} / {items.length}
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
          src={getScreenshotUrl(item.filename, item.subdir)}
          alt={`Test sample ${index + 1}`}
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
