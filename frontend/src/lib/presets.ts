import type { Preset } from '../types';

const STORAGE_KEY = 'armor-recommendations-presets';

export function getPresets(): Preset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (p): p is Preset =>
        p != null &&
        typeof p === 'object' &&
        typeof (p as Preset).id === 'string' &&
        typeof (p as Preset).name === 'string' &&
        typeof (p as Preset).preferences === 'object'
    );
  } catch {
    return [];
  }
}

function writePresets(presets: Preset[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
}

export function savePreset(preset: Omit<Preset, 'id'>): Preset {
  const withId: Preset = {
    ...preset,
    id: crypto.randomUUID(),
  };
  const presets = getPresets();
  presets.push(withId);
  writePresets(presets);
  return withId;
}

export function deletePreset(id: string): void {
  const presets = getPresets().filter((p) => p.id !== id);
  writePresets(presets);
}
