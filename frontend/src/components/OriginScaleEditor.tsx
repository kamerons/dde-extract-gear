import { useCallback, useEffect, useRef, useState } from 'react';
import {
  listScreenshots,
  getScreenshotUrl,
  getScreenshotOrigin,
  fetchBoxes,
  getExtractConfig,
  saveOrigin,
  EXTRACT_SUBDIRS,
  type ImageType,
  type ExtractBox,
  type ExtractConfigResponse,
  type TranslationMarginLines,
} from '../api/extract';

const DISPLAY_SCALE = 0.5;

export interface OriginScaleEditorProps {
  /** When true, show the scale number input. When false, use backend scale for overlay. */
  showScaleInput?: boolean;
  /** When true, show the Save origin button and status. */
  showSaveOriginButton?: boolean;
  /** When true, show the augmentation preview section (Configuration tab only). */
  showAugmentPreview?: boolean;
  /** When true (e.g. Training tab), load a random unlabeled image on init and after Enter-after-save; arrow keys nudge origin, Enter saves then loads next. */
  preferUnlabeledRandom?: boolean;
  /** Called after origin is saved successfully; e.g. parent can refetch training data counts. */
  onOriginSaved?: () => void;
  /** When true (e.g. Training tab), show "Show cropped area" checkbox; when checked, overlay black bars and replace Origin/Scale with config form. */
  showCroppedAreaOption?: boolean;
}

type SubdirItem = { subdir: string; filename: string; hasOrigin: boolean };

export function OriginScaleEditor({
  showScaleInput = true,
  showSaveOriginButton = true,
  showAugmentPreview = false,
  preferUnlabeledRandom = false,
  onOriginSaved,
  showCroppedAreaOption = false,
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
  const [marginLines, setMarginLines] = useState<TranslationMarginLines | null>(null);
  const [boxesError, setBoxesError] = useState<string | null>(null);
  const [imageNaturalSize, setImageNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const [extractConfig, setExtractConfig] = useState<ExtractConfigResponse | null>(null);
  const [saveStatus, setSaveStatus] = useState<'success' | 'error' | null>(null);
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);
  const [previewAugment, setPreviewAugment] = useState<boolean>(false);
  const [showCroppedArea, setShowCroppedArea] = useState<boolean>(false);
  const [localConfig, setLocalConfig] = useState<{
    regular_scale: number;
    blueprint_scale: number;
    augment_fill: string;
    augment_count: number;
    augment_shift_regular: ExtractConfigResponse['augment_shift_regular'];
    augment_shift_blueprint: ExtractConfigResponse['augment_shift_blueprint'];
  }>({
    regular_scale: 1.0,
    blueprint_scale: 1.0,
    augment_fill: 'black',
    augment_count: 3,
    augment_shift_regular: { x_neg: 0.15, x_pos: 0.15, y_neg: 0.15, y_pos: 0.15 },
    augment_shift_blueprint: { x_neg: 0.2, x_pos: 0.2, y_neg: 0.2, y_pos: 0.2 },
  });
  const imageRef = useRef<HTMLImageElement | null>(null);
  const previewCanvasPosRef = useRef<HTMLCanvasElement | null>(null);
  const previewCanvasNegRef = useRef<HTMLCanvasElement | null>(null);
  const imageContainerRef = useRef<HTMLDivElement | null>(null);
  const enterNextLoadsNewImageRef = useRef<boolean>(false);
  const initialLoadDoneRef = useRef<boolean>(false);

  const backendScale =
    imageType === 'blueprint'
      ? (extractConfig?.blueprint_scale ?? 1.0)
      : (extractConfig?.regular_scale ?? 1.0);
  const currentScale = showScaleInput
    ? imageType === 'blueprint'
      ? blueprintScale
      : regularScale
    : backendScale;

  const loadScreenshots = useCallback(async (overrideType?: ImageType) => {
    const type = overrideType ?? imageType;
    const subdir =
      type === 'blueprint' ? EXTRACT_SUBDIRS.blueprint : EXTRACT_SUBDIRS.regular;
    try {
      const res = await listScreenshots(subdir);
      setFilenames(res.filenames);
      setHasOriginSet(new Set(res.has_origin ?? []));
      if (overrideType != null) {
        setImageType(type);
      }
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

  const loadBothAndSelectRandomUnlabeled = useCallback(async () => {
    try {
      const [resRegular, resBlueprint] = await Promise.all([
        listScreenshots(EXTRACT_SUBDIRS.regular),
        listScreenshots(EXTRACT_SUBDIRS.blueprint),
      ]);
      const hasOriginRegular = new Set(resRegular.has_origin ?? []);
      const hasOriginBlueprint = new Set(resBlueprint.has_origin ?? []);
      const items: SubdirItem[] = [
        ...resRegular.filenames.map((filename) => ({
          subdir: EXTRACT_SUBDIRS.regular,
          filename,
          hasOrigin: hasOriginRegular.has(filename),
        })),
        ...resBlueprint.filenames.map((filename) => ({
          subdir: EXTRACT_SUBDIRS.blueprint,
          filename,
          hasOrigin: hasOriginBlueprint.has(filename),
        })),
      ];
      if (items.length === 0) {
        setFilenames([]);
        setHasOriginSet(new Set());
        setImageType('regular');
        setSelectedFilename(null);
        setOriginX(0);
        setOriginY(0);
        return;
      }
      const unlabeled = items.filter((i) => !i.hasOrigin);
      const pick =
        unlabeled.length > 0
          ? unlabeled[Math.floor(Math.random() * unlabeled.length)]
          : items[0];
      const isBlueprint = pick.subdir === EXTRACT_SUBDIRS.blueprint;
      setImageType(isBlueprint ? 'blueprint' : 'regular');
      setFilenames(
        isBlueprint ? resBlueprint.filenames : resRegular.filenames
      );
      setHasOriginSet(
        new Set(
          isBlueprint ? resBlueprint.has_origin ?? [] : resRegular.has_origin ?? []
        )
      );
      setSelectedFilename(pick.filename);
      setOriginX(0);
      setOriginY(0);
    } catch (e) {
      console.error('Failed to load screenshots for random unlabeled', e);
      setFilenames([]);
      setHasOriginSet(new Set());
      setSelectedFilename(null);
    }
  }, []);

  useEffect(() => {
    if (preferUnlabeledRandom) {
      if (initialLoadDoneRef.current) return;
      initialLoadDoneRef.current = true;
      loadBothAndSelectRandomUnlabeled();
      return;
    }
    initialLoadDoneRef.current = false;
    loadScreenshots();
  }, [preferUnlabeledRandom, loadScreenshots, loadBothAndSelectRandomUnlabeled]);

  useEffect(() => {
    if (!showScaleInput || showAugmentPreview || showCroppedAreaOption) {
      getExtractConfig()
        .then(setExtractConfig)
        .catch((e) => console.error('Failed to fetch extract config', e));
    }
  }, [showScaleInput, showAugmentPreview, showCroppedAreaOption]);

  useEffect(() => {
    if (!extractConfig) return;
    setLocalConfig({
      regular_scale: extractConfig.regular_scale,
      blueprint_scale: extractConfig.blueprint_scale,
      augment_fill: extractConfig.augment_fill,
      augment_count: extractConfig.augment_count,
      augment_shift_regular: { ...extractConfig.augment_shift_regular },
      augment_shift_blueprint: { ...extractConfig.augment_shift_blueprint },
    });
  }, [extractConfig]);

  useEffect(() => {
    if (!selectedFilename) {
      setBoxes([]);
      setMarginLines(null);
      setBoxesError(null);
      return;
    }
    let cancelled = false;
    setBoxesError(null);
    const opts =
      imageNaturalSize != null
        ? { imageWidth: imageNaturalSize.width, imageHeight: imageNaturalSize.height }
        : undefined;
    fetchBoxes(originX, originY, currentScale, imageType, opts)
      .then((res) => {
        if (!cancelled) {
          setBoxes(res.boxes);
          setMarginLines(res.translation_margin_lines ?? null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setBoxesError(err instanceof Error ? err.message : 'Failed to fetch boxes');
          setBoxes([]);
          setMarginLines(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [originX, originY, currentScale, imageType, selectedFilename, imageNaturalSize]);

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
    const bounds =
      imageType === 'blueprint'
        ? extractConfig.augment_shift_blueprint
        : extractConfig.augment_shift_regular;
    const dxNeg = -Math.max(0, Math.round(w * bounds.x_neg));
    const dyNeg = -Math.max(0, Math.round(h * bounds.y_neg));
    const dxPos = Math.max(0, Math.round(w * bounds.x_pos));
    const dyPos = Math.max(0, Math.round(h * bounds.y_pos));

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

    drawShifted(previewCanvasNegRef.current, dxNeg, dyNeg);
    drawShifted(previewCanvasPosRef.current, dxPos, dyPos);
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
    target.focus();
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
      if (preferUnlabeledRandom) {
        enterNextLoadsNewImageRef.current = true;
      }
    } catch (e) {
      setSaveStatus('error');
      setSaveErrorMessage(e instanceof Error ? e.message : 'Failed to save origin');
    }
  }, [selectedFilename, screenshotSubdir, originX, originY, loadScreenshots, onOriginSaved, preferUnlabeledRandom]);

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

  // When user selects a different screenshot, load its saved origin if it has one.
  useEffect(() => {
    if (!selectedFilename || !isLabeledSubdir) return;
    if (!hasOriginSet.has(selectedFilename)) {
      setOriginX(0);
      setOriginY(0);
      return;
    }
    let cancelled = false;
    getScreenshotOrigin(selectedFilename, screenshotSubdir)
      .then(({ origin_x, origin_y }) => {
        if (!cancelled) {
          setOriginX(origin_x);
          setOriginY(origin_y);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          console.error('Failed to load saved origin', e);
          setOriginX(0);
          setOriginY(0);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedFilename, screenshotSubdir, isLabeledSubdir, hasOriginSet]);

  const handleImageKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const step = e.shiftKey ? 5 : 1;
      const w = imageNaturalSize?.width ?? Infinity;
      const h = imageNaturalSize?.height ?? Infinity;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        e.stopPropagation();
        setOriginX((prev) => Math.max(0, prev - step));
        return;
      }
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        e.stopPropagation();
        setOriginX((prev) => Math.min(w, prev + step));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        e.stopPropagation();
        setOriginY((prev) => Math.max(0, prev - step));
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        e.stopPropagation();
        setOriginY((prev) => Math.min(h, prev + step));
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        if (enterNextLoadsNewImageRef.current) {
          enterNextLoadsNewImageRef.current = false;
          loadBothAndSelectRandomUnlabeled().then(() => {
            setTimeout(() => imageContainerRef.current?.focus(), 0);
          });
          return;
        }
        if (canSaveOrigin) {
          handleSaveOrigin();
        }
        return;
      }
      if (e.key === ' ') {
        e.preventDefault();
      }
    },
    [
      imageNaturalSize?.width,
      imageNaturalSize?.height,
      handleSaveOrigin,
      loadBothAndSelectRandomUnlabeled,
      canSaveOrigin,
    ]
  );

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
          {showCroppedAreaOption && (
            <label className="extract-config-form-label extract-config-cropped-area-toggle">
              <input
                type="checkbox"
                checked={showCroppedArea}
                onChange={(e) => setShowCroppedArea(e.target.checked)}
              />
              Show cropped area
            </label>
          )}
          <p className="stat-section-label">
            {showCroppedArea ? 'Extract config (for this image type)' : 'Set origin and scale'}
          </p>
          <label className="extract-config-form-label">
            Image type
            <select
              value={imageType}
              onChange={(e) => {
                const newType = e.target.value as ImageType;
                setImageType(newType);
                if (preferUnlabeledRandom) {
                  loadScreenshots(newType);
                }
              }}
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
          {showCroppedArea ? (
            <>
              {extractConfig == null && (
                <p className="stat-section-description" role="status">Loading config…</p>
              )}
              <label className="extract-config-form-label">
                Scale ({imageType === 'blueprint' ? 'blueprint' : 'regular'})
                <input
                  type="number"
                  min={0.1}
                  max={3}
                  step={0.01}
                  value={imageType === 'blueprint' ? localConfig.blueprint_scale : localConfig.regular_scale}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setLocalConfig((prev) =>
                      imageType === 'blueprint'
                        ? { ...prev, blueprint_scale: v }
                        : { ...prev, regular_scale: v }
                    );
                  }}
                  className="extract-config-number"
                />
              </label>
              <label className="extract-config-form-label">
                Augment fill
                <select
                  value={localConfig.augment_fill}
                  onChange={(e) => setLocalConfig((prev) => ({ ...prev, augment_fill: e.target.value }))}
                  className="extract-config-select"
                >
                  <option value="black">black</option>
                  <option value="noise">noise</option>
                </select>
              </label>
              <label className="extract-config-form-label">
                Augment count
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={localConfig.augment_count}
                  onChange={(e) =>
                    setLocalConfig((prev) => ({ ...prev, augment_count: Number(e.target.value) || 1 }))
                  }
                  className="extract-config-number"
                />
              </label>
              <p className="stat-section-label extract-config-shift-label">
                Shift bounds
              </p>
              {(['x_neg', 'x_pos', 'y_neg', 'y_pos'] as const).map((key) => {
                const bounds = imageType === 'blueprint' ? localConfig.augment_shift_blueprint : localConfig.augment_shift_regular;
                return (
                  <label key={key} className="extract-config-form-label">
                    {key}
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={bounds[key]}
                      onChange={(e) => {
                        const v = Number(e.target.value);
                        setLocalConfig((prev) => ({
                          ...prev,
                          [imageType === 'blueprint' ? 'augment_shift_blueprint' : 'augment_shift_regular']: {
                            ...(imageType === 'blueprint' ? prev.augment_shift_blueprint : prev.augment_shift_regular),
                            [key]: v,
                          },
                        }));
                      }}
                      className="extract-config-number"
                    />
                  </label>
                );
              })}
            </>
          ) : (
            <>
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
            </>
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
            ref={imageContainerRef}
            className="extract-config-image-container"
            style={{
              width: displayWidth || 'auto',
              height: displayHeight || 'auto',
            }}
            onClick={handleImageClick}
            onKeyDown={handleImageKeyDown}
            role="button"
            tabIndex={0}
            aria-label="Click to set top-left corner of armor tab. Use arrow keys to nudge, Enter to save or load next image."
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
            {showCroppedArea && extractConfig != null && imageNaturalSize && displayWidth > 0 && displayHeight > 0 && (() => {
              const bounds = imageType === 'blueprint' ? localConfig.augment_shift_blueprint : localConfig.augment_shift_regular;
              const leftW = displayWidth * bounds.x_neg;
              const rightW = displayWidth * bounds.x_pos;
              const topH = displayHeight * bounds.y_neg;
              const bottomH = displayHeight * bounds.y_pos;
              const scaleToDisplay = displayWidth / imageNaturalSize.width;
              const toDisplayX = (cx: number) => leftW + cx * scaleToDisplay;
              const toDisplayY = (cy: number) => topH + cy * scaleToDisplay;
              return (
                <svg
                  className="extract-config-cropped-area-overlay"
                  width={displayWidth}
                  height={displayHeight}
                  style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
                  aria-hidden
                >
                  <defs>
                    <marker
                      id="extract-config-margin-arrow"
                      markerWidth={10}
                      markerHeight={10}
                      refX={9}
                      refY={3}
                      orient="auto"
                      markerUnits="strokeWidth"
                    >
                      <path d="M0,0 L0,6 L9,3 z" className="extract-config-translation-margin-arrow" />
                    </marker>
                  </defs>
                  <rect x={0} y={0} width={leftW} height={displayHeight} className="extract-config-cropped-bar" />
                  <rect x={displayWidth - rightW} y={0} width={rightW} height={displayHeight} className="extract-config-cropped-bar" />
                  <rect x={0} y={0} width={displayWidth} height={topH} className="extract-config-cropped-bar" />
                  <rect x={0} y={displayHeight - bottomH} width={displayWidth} height={bottomH} className="extract-config-cropped-bar" />
                  {marginLines && (
                    <>
                      <line x1={toDisplayX(marginLines.left.x1)} y1={toDisplayY(marginLines.left.y1)} x2={toDisplayX(marginLines.left.x2)} y2={toDisplayY(marginLines.left.y2)} className="extract-config-translation-margin-line" markerEnd="url(#extract-config-margin-arrow)" />
                      <line x1={toDisplayX(marginLines.top.x1)} y1={toDisplayY(marginLines.top.y1)} x2={toDisplayX(marginLines.top.x2)} y2={toDisplayY(marginLines.top.y2)} className="extract-config-translation-margin-line" markerEnd="url(#extract-config-margin-arrow)" />
                      <line x1={toDisplayX(marginLines.right.x1)} y1={toDisplayY(marginLines.right.y1)} x2={toDisplayX(marginLines.right.x2)} y2={toDisplayY(marginLines.right.y2)} className="extract-config-translation-margin-line" markerEnd="url(#extract-config-margin-arrow)" />
                      <line x1={toDisplayX(marginLines.bottom.x1)} y1={toDisplayY(marginLines.bottom.y1)} x2={toDisplayX(marginLines.bottom.x2)} y2={toDisplayY(marginLines.bottom.y2)} className="extract-config-translation-margin-line" markerEnd="url(#extract-config-margin-arrow)" />
                    </>
                  )}
                </svg>
              );
            })()}
            {!showCroppedArea && (originX !== 0 || originY !== 0) ? (
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
            Shows how the current shift bounds (x_neg, x_pos, y_neg, y_pos for {imageType}) will
            affect this image. Left: negative shift; right: positive shift. Uses black fill.
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
