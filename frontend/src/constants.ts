import type { StatType } from './types';

// All available stat types
export const ALL_STATS: StatType[] = [
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
];

// Human-readable display names for stats
export const STAT_DISPLAY_NAMES: Record<StatType, string> = {
  base: 'Base Resistance',
  fire: 'Fire Resistance',
  electric: 'Electric Resistance',
  poison: 'Poison Resistance',
  hero_hp: 'Hero HP',
  hero_dmg: 'Hero Damage',
  hero_rate: 'Hero Cast Rate',
  hero_speed: 'Hero Speed',
  offense: 'Offense',
  defense: 'Defense',
  tower_hp: 'Tower HP',
  tower_dmg: 'Tower Damage',
  tower_rate: 'Tower Rate',
  tower_range: 'Tower Range',
};

// Stat categories for visual grouping
export type StatCategory = 'resistance' | 'hero' | 'combat' | 'tower';

export interface StatCategoryInfo {
  name: string;
  stats: StatType[];
}

export const STAT_CATEGORIES: Record<StatCategory, StatCategoryInfo> = {
  resistance: {
    name: 'Resistance',
    stats: ['base', 'fire', 'electric', 'poison'],
  },
  hero: {
    name: 'Hero',
    stats: ['hero_hp', 'hero_dmg', 'hero_rate', 'hero_speed'],
  },
  combat: {
    name: 'Combat',
    stats: ['offense', 'defense'],
  },
  tower: {
    name: 'Tower',
    stats: ['tower_hp', 'tower_dmg', 'tower_rate', 'tower_range'],
  },
};

// Get display name for a stat
export function getStatDisplayName(stat: StatType): string {
  return STAT_DISPLAY_NAMES[stat];
}

// Get category for a stat
export function getStatCategory(stat: StatType): StatCategory | null {
  for (const [category, info] of Object.entries(STAT_CATEGORIES)) {
    if (info.stats.includes(stat)) {
      return category as StatCategory;
    }
  }
  return null;
}
