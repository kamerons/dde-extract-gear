/**
 * Shared stat-type constants, display order, and hotkey helpers for stat icon labeling and verification.
 */

export const ARMOR_STATS = ['base', 'fire', 'electric', 'poison'] as const;
export const TOWER_STATS = ['tower_hp', 'tower_dmg', 'tower_rate', 'tower_range'] as const;
export const HERO_STATS = ['hero_hp', 'hero_dmg', 'hero_rate', 'offense', 'defense', 'hero_speed'] as const;

export function statTypeToFriendlyLabel(statType: string): string {
  if (statType === 'none') return 'None';
  if (statType === 'unlabeled') return 'Unlabeled';
  return statType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

export function getHotkeyForStatType(statType: string): string | null {
  if (statType === 'none') return 'Space';
  const armorIdx = ARMOR_STATS.indexOf(statType as (typeof ARMOR_STATS)[number]);
  if (armorIdx >= 0) return `Ctrl+${armorIdx + 1}`;
  const towerIdx = TOWER_STATS.indexOf(statType as (typeof TOWER_STATS)[number]);
  if (towerIdx >= 0) return String(towerIdx + 1);
  const heroIdx = HERO_STATS.indexOf(statType as (typeof HERO_STATS)[number]);
  if (heroIdx >= 0) return `Alt+${heroIdx + 1}`;
  return null;
}

export function parseHotkeyToStatType(
  key: string,
  shiftKey: boolean,
  ctrlKey: boolean,
  altKey: boolean
): string | null {
  if (key === ' ' || key === 'Spacebar') return 'none';
  if (key >= '1' && key <= '4' && ctrlKey && !shiftKey && !altKey) {
    const i = parseInt(key, 10) - 1;
    return ARMOR_STATS[i] ?? null;
  }
  if (key >= '1' && key <= '4' && !shiftKey && !ctrlKey && !altKey) {
    const i = parseInt(key, 10) - 1;
    return TOWER_STATS[i] ?? null;
  }
  if (key >= '1' && key <= '6' && altKey && !shiftKey && !ctrlKey) {
    const i = parseInt(key, 10) - 1;
    return HERO_STATS[i] ?? null;
  }
  return null;
}

export const BUTTON_GROUPS: { types: readonly string[] }[] = [
  { types: ['none'] },
  { types: ARMOR_STATS },
  { types: TOWER_STATS },
  { types: HERO_STATS },
];

/** Display order for verification: unlabeled first, then none, armor, tower, hero. */
export const VERIFY_TYPE_ORDER: string[] = [
  'unlabeled',
  'none',
  ...ARMOR_STATS,
  ...TOWER_STATS,
  ...HERO_STATS,
];
