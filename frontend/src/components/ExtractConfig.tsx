import { useCallback, useEffect, useState } from 'react';
import {
  listScreenshots,
  getScreenshotUrl,
  fetchBoxes,
  EXTRACT_SUBDIRS,
  type ImageType,
  type ExtractBox,
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

        <div className="configuration-section extract-config-env">
          <p className="stat-section-label">Add these to your .env</p>
          <p className="stat-section-description">
            Copy these lines into your .env file. Only the scale factors are stored; origin is
            provided by the box detector at inference time.
          </p>
          <pre className="extract-config-env-block">
            EXTRACT_REGULAR_SCALE={regularScale}
            {'\n'}
            EXTRACT_BLUEPRINT_SCALE={blueprintScale}
          </pre>
        </div>
      </div>
    </div>
  );
}
