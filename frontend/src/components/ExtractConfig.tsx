import { useEffect, useState } from 'react';
import { getExtractConfig, type ExtractConfigResponse } from '../api/extract';
import { OriginScaleEditor } from './OriginScaleEditor';

export function ExtractConfig() {
  const [extractConfig, setExtractConfig] = useState<ExtractConfigResponse | null>(null);

  useEffect(() => {
    getExtractConfig()
      .then(setExtractConfig)
      .catch((e) => console.error('Failed to fetch extract config', e));
  }, []);

  const regularScale = extractConfig?.regular_scale ?? 1.0;
  const blueprintScale = extractConfig?.blueprint_scale ?? 1.0;

  return (
    <div className="configuration-container extract-config">
      <div className="configuration-header">
        <h1>Configuration</h1>
        <p className="header-description">
          Set the top-left corner of the armor tab and scaling so region overlays align. Origin is
          temporary (the box detector will provide it later). Copy the scale values to your .env.
        </p>
      </div>

      <div className="configuration-sections">
        <OriginScaleEditor
          showScaleInput={true}
          showSaveOriginButton={true}
          showAugmentPreview={true}
        />
        <div className="configuration-section extract-config-env">
          <p className="stat-section-label">Add these to your .env</p>
          <p className="stat-section-description">
            Copy these lines into your .env file. Scale and augmentation are used by the server
            and by box detector training; origin is saved per image via Save origin.
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
