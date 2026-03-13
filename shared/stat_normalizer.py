"""Stat normalization using reference scales for relative strength comparison."""

from functools import lru_cache


class StatNormalizer:
    """
    Normalizes stats using reference scales so that relative strength is comparable
    across armors. Values are not capped: normalized = value / reference_scale(stat),
    so values above the reference scale produce normalized > 1.0.

    Uses simple relative ratios between groups (not observed caps) so future stronger
    gear still maps sensibly. Same group = same reference scale so 0.5 means similar
    relative strength for any stat in that group. Ratios are based on cleaned data
    (outlier records removed; see scripts/clean_armor_outliers.py).

    Groups and reference scales (max_val in STAT_GROUPS):
    - Reference scale 50: fire/electric/poison and all hero/tower stats (0, 50).
    - Base resistance ~3x reference -> (0, 150).
    - Hero speed ~0.5x reference -> (0, 25).
    """

    # Fire/Electric/Poison and all Hero/Tower stats (same scale on cleaned data)
    RESISTANCE_RANGE = (0, 50)
    HERO_TOWER_RANGE = (0, 50)

    # Base resistance ~3x reference
    BASE_RANGE = (0, 150)

    # Hero speed - half reference (raw scale ~0.2x other hero/tower stats)
    SPEED_RANGE = (0, 25)

    # Map stats to their normalization groups (min, max) with min=0; max is reference scale
    STAT_GROUPS = {
        'base': BASE_RANGE,
        'fire': RESISTANCE_RANGE,
        'electric': RESISTANCE_RANGE,
        'poison': RESISTANCE_RANGE,
        'hero_hp': HERO_TOWER_RANGE,
        'hero_dmg': HERO_TOWER_RANGE,
        'hero_rate': HERO_TOWER_RANGE,
        'hero_speed': SPEED_RANGE,
        'offense': HERO_TOWER_RANGE,
        'defense': HERO_TOWER_RANGE,
        'tower_hp': HERO_TOWER_RANGE,
        'tower_dmg': HERO_TOWER_RANGE,
        'tower_rate': HERO_TOWER_RANGE,
        'tower_range': HERO_TOWER_RANGE,
    }

    @lru_cache(maxsize=100000)
    def normalize_stat(self, stat_name: str, value: int) -> float:
        """
        Normalize a stat value using the group reference scale. No upper cap:
        values above the reference scale yield normalized > 1.0.

        Args:
            stat_name: Name of the stat
            value: Raw stat value

        Returns:
            Normalized value (value / reference_scale). >= 0; may exceed 1.0.
        """
        if stat_name not in self.STAT_GROUPS:
            return 0.0

        min_val, max_val = self.STAT_GROUPS[stat_name]
        if max_val == min_val:
            return 0.0

        # Reference scale only; no upper clamp so stronger gear can exceed 1.0
        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, normalized)
