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

export interface RecommendationPiece {
  armor_set: string;
  armor_type: string;
  current_level: number;
  max_level: number;
  stats: Record<string, number>;
}

export interface Recommendation {
  set_id: string;
  pieces: RecommendationPiece[];
  current_stats: Record<string, number>;
  upgraded_stats: Record<string, number>;
  effective_stats: Record<string, number>;
  wasted_points: Record<string, number>;
  score: number;
  potential_score: number;
  flexibility_score: number;
}
