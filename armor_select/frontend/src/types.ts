// Type definitions for armor selection system

export const STAT_TYPES = [
  'base',
  'fire',
  'electric',
  'poison',
  'hero_hp',
  'hero_dmg',
  'hero_rate',
  'hero_speed',
  'offense',
  'defense',
  'tower_hp',
  'tower_dmg',
  'tower_rate',
  'tower_range',
] as const;

export type StatType = (typeof STAT_TYPES)[number];

export interface BuildPreferences {
  maximizeStats: StatType[];
  ignoreStats: StatType[];
  minConstraints: Record<StatType, number>;
  softCaps: Record<StatType, number>;
}
