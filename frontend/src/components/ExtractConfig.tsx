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

export function ExtractConfig() {
  const [imageType, setImageType] = useState<ImageType>('regular');
  const [filenames, setFilenames] = useState<string[]>([]);
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

  const currentScale = imageType === 'blueprint' ? blueprintScale : regularScale;

  const loadScreenshots = useCallback(async () => {
    const subdir =
      imageType === 'blueprint' ? EXTRACT_SUBDIRS.blueprint : EXTRACT_SUBDIRS.regular;
    try {
      const { filenames: list } = await listScreenshots(subdir);
      setFilenames(list);
      if (list.length > 0) {
        setSelectedFilename((prev) =>
          prev && list.includes(prev) ? prev : list[0]
        );
      } else {
        setSelectedFilename(null);
      }
    } catch (e) {
      console.error('Failed to list screenshots', e);
      setFilenames([]);
      setSelectedFilename(null);
    }
  }, [imageType]);

  useEffect(() => {
    loadScreenshots();
  }, [loadScreenshots]);

  useEffect(() => {
    getExtractConfig()
      .then(setExtractConfig)
      .catch((e) => console.error('Failed to fetch extract config', e));
  }, []);

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

  // Draw augmentation preview (positive and negative shift) when toggle is on and image is loaded
  useEffect(() => {
    if (
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
    } catch (e) {
      setSaveStatus('error');
      setSaveErrorMessage(e instanceof Error ? e.message : 'Failed to save origin');
    }
  }, [selectedFilename, screenshotSubdir, originX, originY]);

  const isLabeledSubdir =
    screenshotSubdir === EXTRACT_SUBDIRS.regular ||
    screenshotSubdir === EXTRACT_SUBDIRS.blueprint;
  const canSaveOrigin = isLabeledSubdir && selectedFilename != null;

  const imageUrl = selectedFilename
    ? getScreenshotUrl(selectedFilename, screenshotSubdir)
    : null;
  const displayWidth = imageNaturalSize ? imageNaturalSize.width * DISPLAY_SCALE : 0;
  const displayHeight = imageNaturalSize ? imageNaturalSize.height * DISPLAY_SCALE : 0;

  return (
    <div className="configuration-container extract-config">
      <div className="configuration-header">
        <h1>Extract configuration</h1>
        <p className="header-description">
          Set the top-left corner of the armor tab and scaling so region overlays align. Origin is
          temporary (the box detector will provide it later). Copy the scale values to your .env.
        </p>
      </div>

      <div className="configuration-sections">
        <div className="configuration-section extract-config-controls">
          <div className="extract-config-row">
            <label>
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
            <label>
              Screenshot
              <select
                value={selectedFilename ?? ''}
                onChange={(e) => setSelectedFilename(e.target.value || null)}
                className="extract-config-select"
              >
                {filenames.length === 0 && <option value="">No screenshots</option>}
                {filenames.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="configuration-section extract-config-image-section">
          <p className="stat-section-label">Set origin and scale</p>
          <p className="stat-section-description">
            Click on the image to set the top-left corner of the armor tab, or edit the numbers
            below. Adjust the scaling factor until the overlays align with the regions.
          </p>
          <div className="extract-config-origin-inputs">
            <label>
              Origin X (px)
              <input
                type="number"
                value={originX}
                onChange={(e) => setOriginX(Number(e.target.value) || 0)}
                className="extract-config-number"
              />
            </label>
            <label>
              Origin Y (px)
              <input
                type="number"
                value={originY}
                onChange={(e) => setOriginY(Number(e.target.value) || 0)}
                className="extract-config-number"
              />
            </label>
          </div>
          <div className="extract-config-scale-input">
            <label>
              Scale ({imageType === 'blueprint' ? 'blueprint' : 'regular'})
              <input
                type="number"
                min={0.1}
                max={3}
                step={0.01}
                value={imageType === 'blueprint' ? blueprintScale : regularScale}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (imageType === 'blueprint') setBlueprintScale(v); else setRegularScale(v);
                }}
                className="extract-config-number"
              />
            </label>
          </div>
          {canSaveOrigin && (
            <div className="extract-config-save-row">
              <button
                type="button"
                className="extract-config-save-button"
                onClick={handleSaveOrigin}
              >
                Save origin
              </button>
              {saveStatus === 'success' && (
                <span className="extract-config-save-ok" role="status">
                  Saved
                </span>
              )}
              {saveStatus === 'error' && (
                <span className="configuration-error" role="alert">
                  {saveErrorMessage ?? 'Failed to save'}
                </span>
              )}
            </div>
          )}
          {boxesError && (
            <p className="configuration-error" role="alert">
              {boxesError}
            </p>
          )}
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

          {extractConfig && (
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
        </div>

        <div className="configuration-section extract-config-env">
          <p className="stat-section-label">Add these to your .env</p>
          <p className="stat-section-description">
            Copy these lines into your .env file. Scale and augmentation shift are used by the
            server and the augmentation script; origin is saved per image via Save origin.
          </p>
          <pre className="extract-config-env-block">
            EXTRACT_REGULAR_SCALE={extractConfig?.regular_scale ?? regularScale}
            {'\n'}
            EXTRACT_BLUEPRINT_SCALE={extractConfig?.blueprint_scale ?? blueprintScale}
            {extractConfig != null && (
              <>
                {'\n'}
                EXTRACT_AUGMENT_SHIFT_REGULAR={extractConfig.augment_shift_regular}
                {'\n'}
                EXTRACT_AUGMENT_SHIFT_BLUEPRINT={extractConfig.augment_shift_blueprint}
                {'\n'}
                EXTRACT_AUGMENT_FILL={extractConfig.augment_fill}
              </>
            )}
          </pre>
        </div>
      </div>
    </div>
  );
}
