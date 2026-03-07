import { useCallback, useEffect, useRef, useState } from 'react';
import {
  listScreenshots,
  getScreenshotUrl,
  fetchBoxes,
  getExtractConfig,
  saveOrigin,
  EXTRACT_SUBDIRS,
  type ImageType,
  type ExtractBox,
  type ExtractConfigResponse,
} from '../api/extract';

const DISPLAY_SCALE = 0.5;

export interface OriginScaleEditorProps {
  /** When true, show the scale number input. When false, use backend scale for overlay. */
  showScaleInput?: boolean;
  /** When true, show the Save origin button and status. */
  showSaveOriginButton?: boolean;
  /** When true, show the augmentation preview section (Configuration tab only). */
  showAugmentPreview?: boolean;
  /** Called after origin is saved successfully; e.g. parent can refetch training data counts. */
  onOriginSaved?: () => void;
}

export function OriginScaleEditor({
  showScaleInput = true,
  showSaveOriginButton = true,
  showAugmentPreview = false,
  onOriginSaved,
}: OriginScaleEditorProps) {
  const [imageType, setImageType] = useState<ImageType>('regular');
  const [filenames, setFilenames] = useState<string[]>([]);
  const [hasOriginSet, setHasOriginSet] = useState<Set<string>>(new Set());
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [originX, setOriginX] = useState<number>(0);
  const [originY, setOriginY] = useState<number>(0);
  const [regularScale, setRegularScale] = useState<number>(1.0);
  const [blueprintScale, setBlueprintScale] = useState<number>(1.0);
  const [boxes, setBoxes] = useState<ExtractBox[]>([]);
  const [boxesError, setBoxesError] = useState<string | null>(null);
  const [imageNaturalSize, setImageNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const [extractConfig, setExtractConfig] = useState<ExtractConfigResponse | null>(null);
  const [saveStatus, setSaveStatus] = useState<'success' | 'error' | null>(null);
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);
  const [previewAugment, setPreviewAugment] = useState<boolean>(false);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const previewCanvasPosRef = useRef<HTMLCanvasElement | null>(null);
  const previewCanvasNegRef = useRef<HTMLCanvasElement | null>(null);

  const backendScale =
    imageType === 'blueprint'
      ? (extractConfig?.blueprint_scale ?? 1.0)
      : (extractConfig?.regular_scale ?? 1.0);
  const currentScale = showScaleInput
    ? imageType === 'blueprint'
      ? blueprintScale
      : regularScale
    : backendScale;

  const loadScreenshots = useCallback(async () => {
    const subdir =
      imageType === 'blueprint' ? EXTRACT_SUBDIRS.blueprint : EXTRACT_SUBDIRS.regular;
    try {
      const res = await listScreenshots(subdir);
      setFilenames(res.filenames);
      setHasOriginSet(new Set(res.has_origin ?? []));
      if (res.filenames.length > 0) {
        setSelectedFilename((prev) =>
          prev && res.filenames.includes(prev) ? prev : res.filenames[0]
        );
      } else {
        setSelectedFilename(null);
      }
    } catch (e) {
      console.error('Failed to list screenshots', e);
      setFilenames([]);
      setHasOriginSet(new Set());
      setSelectedFilename(null);
    }
  }, [imageType]);

  useEffect(() => {
    loadScreenshots();
  }, [loadScreenshots]);

  useEffect(() => {
    if (!showScaleInput || showAugmentPreview) {
      getExtractConfig()
        .then(setExtractConfig)
        .catch((e) => console.error('Failed to fetch extract config', e));
    }
  }, [showScaleInput, showAugmentPreview]);

  useEffect(() => {
    if (!selectedFilename) {
      setBoxes([]);
      setBoxesError(null);
      return;
    }
    let cancelled = false;
    setBoxesError(null);
    fetchBoxes(originX, originY, currentScale, imageType)
      .then((res) => {
        if (!cancelled) setBoxes(res.boxes);
      })
      .catch((err) => {
        if (!cancelled) {
          setBoxesError(err instanceof Error ? err.message : 'Failed to fetch boxes');
          setBoxes([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [originX, originY, currentScale, imageType, selectedFilename]);

  // Draw augmentation preview when showAugmentPreview is on and image is loaded
  useEffect(() => {
    if (
      !showAugmentPreview ||
      !previewAugment ||
      !imageRef.current?.complete ||
      !extractConfig ||
      !imageNaturalSize
    ) {
      return;
    }
    const img = imageRef.current;
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    const shiftFrac =
      imageType === 'blueprint'
        ? extractConfig.augment_shift_blueprint
        : extractConfig.augment_shift_regular;
    const maxPx = Math.max(1, Math.round(shiftFrac * Math.min(w, h)));

    const drawShifted = (canvas: HTMLCanvasElement | null, dx: number, dy: number) => {
      if (!canvas) return;
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.fillStyle = 'black';
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, dx, dy);
    };

    drawShifted(previewCanvasPosRef.current, maxPx, maxPx);
    drawShifted(previewCanvasNegRef.current, -maxPx, -maxPx);
  }, [
    showAugmentPreview,
    previewAugment,
    imageType,
    extractConfig,
    imageNaturalSize,
    selectedFilename,
  ]);

  const handleImageClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const fullResX = Math.round(x / DISPLAY_SCALE);
    const fullResY = Math.round(y / DISPLAY_SCALE);
    setOriginX(fullResX);
    setOriginY(fullResY);
  };

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
  };

  const screenshotSubdir =
    imageType === 'blueprint' ? EXTRACT_SUBDIRS.blueprint : EXTRACT_SUBDIRS.regular;

  const handleSaveOrigin = useCallback(async () => {
    if (!selectedFilename || !screenshotSubdir) return;
    setSaveStatus(null);
    setSaveErrorMessage(null);
    try {
      await saveOrigin(selectedFilename, screenshotSubdir, originX, originY);
      setSaveStatus('success');
      await loadScreenshots();
      onOriginSaved?.();
    } catch (e) {
      setSaveStatus('error');
      setSaveErrorMessage(e instanceof Error ? e.message : 'Failed to save origin');
    }
  }, [selectedFilename, screenshotSubdir, originX, originY, loadScreenshots, onOriginSaved]);

  useEffect(() => {
    if (saveStatus === null) return;
    const id = setTimeout(() => {
      setSaveStatus(null);
      setSaveErrorMessage(null);
    }, 3000);
    return () => clearTimeout(id);
  }, [saveStatus]);

  const isLabeledSubdir =
    screenshotSubdir === EXTRACT_SUBDIRS.regular ||
    screenshotSubdir === EXTRACT_SUBDIRS.blueprint;
  const canSaveOrigin = isLabeledSubdir && selectedFilename != null;
  const showLabelBadges = isLabeledSubdir && filenames.length > 0;

  const imageUrl = selectedFilename
    ? getScreenshotUrl(selectedFilename, screenshotSubdir)
    : null;
  const displayWidth = imageNaturalSize ? imageNaturalSize.width * DISPLAY_SCALE : 0;
  const displayHeight = imageNaturalSize ? imageNaturalSize.height * DISPLAY_SCALE : 0;

  return (
    <>
      {saveStatus === 'success' && (
        <div
          className="progress-toast"
          role="status"
          aria-live="polite"
        >
          Saved
        </div>
      )}
      {saveStatus === 'error' && (
        <div
          className="progress-toast save-toast-error"
          role="alert"
          aria-live="assertive"
        >
          {saveErrorMessage ?? 'Failed to save'}
        </div>
      )}
      <div className="configuration-section extract-config-origin-layout">
        <div className="extract-config-origin-form">
          <p className="stat-section-label">Set origin and scale</p>
          <label className="extract-config-form-label">
            Image type
            <select
              value={imageType}
              onChange={(e) => setImageType(e.target.value as ImageType)}
              className="extract-config-select"
            >
              <option value="regular">Regular</option>
              <option value="blueprint">Blueprint</option>
            </select>
          </label>
          <div className="extract-config-form-label">
            <span className="extract-config-screenshot-label">Screenshot</span>
            {showLabelBadges && (
              <p className="extract-config-screenshot-summary" aria-live="polite">
                {hasOriginSet.size} of {filenames.length} images have coordinates
              </p>
            )}
            <div
              className="extract-config-screenshot-list"
              role="listbox"
              aria-label="Screenshot"
              tabIndex={0}
            >
              {filenames.length === 0 && (
                <p className="extract-config-no-screenshots-option">No screenshots</p>
              )}
              {filenames.map((f) => (
                <button
                  key={f}
                  type="button"
                  role="option"
                  aria-selected={selectedFilename === f}
                  className={`extract-config-screenshot-row ${selectedFilename === f ? 'extract-config-screenshot-row-selected' : ''}`}
                  onClick={() => setSelectedFilename(f)}
                >
                  <span className="extract-config-screenshot-filename">{f}</span>
                  {showLabelBadges && (
                    <span
                      className={
                        hasOriginSet.has(f)
                          ? 'extract-config-screenshot-badge extract-config-screenshot-badge-labeled'
                          : 'extract-config-screenshot-badge extract-config-screenshot-badge-needs'
                      }
                    >
                      {hasOriginSet.has(f) ? 'Labeled' : 'Needs coordinates'}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
          <label className="extract-config-form-label">
            Origin X (px)
            <input
              type="number"
              value={originX}
              onChange={(e) => setOriginX(Number(e.target.value) || 0)}
              className="extract-config-number"
            />
          </label>
          <label className="extract-config-form-label">
            Origin Y (px)
            <input
              type="number"
              value={originY}
              onChange={(e) => setOriginY(Number(e.target.value) || 0)}
              className="extract-config-number"
            />
          </label>
          {showSaveOriginButton && canSaveOrigin && (
            <button
              type="button"
              className="extract-config-save-button"
              onClick={handleSaveOrigin}
            >
              Save origin
            </button>
          )}
          {showScaleInput && (
            <label className="extract-config-form-label">
              Scale ({imageType === 'blueprint' ? 'blueprint' : 'regular'})
              <input
                type="number"
                min={0.1}
                max={3}
                step={0.01}
                value={imageType === 'blueprint' ? blueprintScale : regularScale}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (imageType === 'blueprint') setBlueprintScale(v);
                  else setRegularScale(v);
                }}
                className="extract-config-number"
              />
            </label>
          )}
          {boxesError && (
            <p className="configuration-error" role="alert">
              {boxesError}
            </p>
          )}
        </div>
        <div className="extract-config-image-wrapper">
        {imageUrl && (
          <div
            className="extract-config-image-container"
            style={{
              width: displayWidth || 'auto',
              height: displayHeight || 'auto',
            }}
            onClick={handleImageClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') e.preventDefault();
            }}
            aria-label="Click to set top-left corner of armor tab"
          >
            <img
              ref={imageRef}
              src={imageUrl}
              alt="Screenshot"
              className="extract-config-image"
              style={{
                width: displayWidth || undefined,
                height: displayHeight || undefined,
              }}
              onLoad={handleImageLoad}
              draggable={false}
            />
            {imageNaturalSize && (
              <svg
                className="extract-config-overlay"
                width={displayWidth}
                height={displayHeight}
                style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
              >
                {boxes.map((b, i) => (
                  <rect
                    key={i}
                    x={b.x * DISPLAY_SCALE}
                    y={b.y * DISPLAY_SCALE}
                    width={b.width * DISPLAY_SCALE}
                    height={b.height * DISPLAY_SCALE}
                    fill="none"
                    stroke={b.type === 'card' ? '#0a0' : b.type === 'set' ? '#06c' : b.type === 'stat' ? '#c60' : '#a0a'}
                    strokeWidth={1.5}
                  />
                ))}
              </svg>
            )}
            {originX !== 0 || originY !== 0 ? (
              <div
                className="extract-config-origin-marker"
                style={{
                  left: originX * DISPLAY_SCALE - 4,
                  top: originY * DISPLAY_SCALE - 4,
                }}
              />
            ) : null}
          </div>
        )}
        {!imageUrl && filenames.length === 0 && (
          <p className="extract-config-no-images">
            No screenshots in data/labeled/screenshots/{imageType}.
          </p>
        )}
        </div>
      </div>

      {showAugmentPreview && extractConfig && (
        <div className="extract-config-augment-section">
          <label className="extract-config-preview-toggle">
            <input
              type="checkbox"
              checked={previewAugment}
              onChange={(e) => setPreviewAugment(e.target.checked)}
            />
            Preview augmentation
          </label>
          <p className="stat-section-description">
            Shows how the current shift level ({imageType === 'blueprint'
              ? extractConfig.augment_shift_blueprint
              : extractConfig.augment_shift_regular}{' '}
            for {imageType}) will affect this image (positive and negative shift). Uses black fill.
          </p>
          {previewAugment && imageNaturalSize && (
            <div className="extract-config-preview-grid">
              <div className="extract-config-preview-cell">
                <p className="extract-config-preview-label">Negative shift (−max)</p>
                <div
                  className="extract-config-preview-wrapper"
                  style={{
                    width: displayWidth || 'auto',
                    height: displayHeight || 'auto',
                  }}
                >
                  <canvas
                    ref={previewCanvasNegRef}
                    width={imageNaturalSize.width}
                    height={imageNaturalSize.height}
                    style={{
                      width: displayWidth || undefined,
                      height: displayHeight || undefined,
                      display: 'block',
                    }}
                    aria-label="Augmentation preview, negative shift"
                  />
                </div>
              </div>
              <div className="extract-config-preview-cell">
                <p className="extract-config-preview-label">Positive shift (+max)</p>
                <div
                  className="extract-config-preview-wrapper"
                  style={{
                    width: displayWidth || 'auto',
                    height: displayHeight || 'auto',
                  }}
                >
                  <canvas
                    ref={previewCanvasPosRef}
                    width={imageNaturalSize.width}
                    height={imageNaturalSize.height}
                    style={{
                      width: displayWidth || undefined,
                      height: displayHeight || undefined,
                      display: 'block',
                    }}
                    aria-label="Augmentation preview, positive shift"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
