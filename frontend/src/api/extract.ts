/**
 * Extract pipeline API: screenshots and region boxes.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export type ImageType = 'regular' | 'blueprint';

export const EXTRACT_SUBDIRS = {
  unlabeled: 'unlabeled/screenshots',
  regular: 'labeled/screenshots/regular',
  blueprint: 'labeled/screenshots/blueprint',
} as const;

export interface ExtractBox {
  x: number;
  y: number;
  width: number;
  height: number;
  type: 'card' | 'set' | 'stat' | 'level';
}

export interface BoxesResponse {
  boxes: ExtractBox[];
}

/**
 * List screenshot filenames in the given subdir.
 */
export async function listScreenshots(
  subdir: string = EXTRACT_SUBDIRS.unlabeled
): Promise<{ filenames: string[] }> {
  const params = new URLSearchParams({ subdir });
  const response = await fetch(`${API_BASE_URL}/api/extract/screenshots?${params}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list screenshots: ${response.status} ${text}`);
  }
  return response.json();
}

/**
 * Return the URL for loading a screenshot image.
 */
export function getScreenshotUrl(
  filename: string,
  subdir: string = EXTRACT_SUBDIRS.unlabeled
): string {
  const params = new URLSearchParams({ subdir });
  return `${API_BASE_URL}/api/extract/screenshots/${encodeURIComponent(filename)}?${params}`;
}

/**
 * Compute region boxes for the first card given origin, scale, and image type.
 * Returns boxes in full-resolution coordinates; scale to 50% in the UI for display.
 */
export async function fetchBoxes(
  originX: number,
  originY: number,
  scale: number,
  imageType: ImageType
): Promise<BoxesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/extract/boxes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin_x: originX,
      origin_y: originY,
      scale,
      image_type: imageType,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch boxes: ${response.status} ${text}`);
  }
  return response.json();
}
