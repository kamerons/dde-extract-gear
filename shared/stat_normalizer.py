"""Stat normalization to 0-1 scale."""

from functools import lru_cache


class StatNormalizer:
    """
    Normalizes stats to 0-1 scale based on known ranges.

    Normalization groups:
    - Base resistance: normalized by itself (0-100)
    - Fire/Electric/Poison resistance: normalized together (0-50)
    - Hero and Tower stats (except speed): normalized together (0-50)
    - Hero speed: normalized by itself (0-100)
    """

    # Base resistance - normalized by itself
    BASE_RANGE = (0, 100)

    # Fire/Electric/Poison resistance - normalized together (same range)
    RESISTANCE_RANGE = (0, 50)

    # Hero and Tower stats (except speed) - normalized together (same range)
    HERO_TOWER_RANGE = (0, 50)

    # Hero speed - normalized by itself
    SPEED_RANGE = (0, 100)

    # Map stats to their normalization groups
    STAT_GROUPS = {
        # Base resistance - by itself
        'base': BASE_RANGE,

        # Fire/Electric/Poison resistance - grouped together
        'fire': RESISTANCE_RANGE,
        'electric': RESISTANCE_RANGE,
        'poison': RESISTANCE_RANGE,

        # Hero stats (except speed) - grouped with tower stats
        'hero_hp': HERO_TOWER_RANGE,
        'hero_dmg': HERO_TOWER_RANGE,
        'hero_rate': HERO_TOWER_RANGE,
        'offense': HERO_TOWER_RANGE,
        'defense': HERO_TOWER_RANGE,

        # Tower stats - grouped with hero stats
        'tower_hp': HERO_TOWER_RANGE,
        'tower_dmg': HERO_TOWER_RANGE,
        'tower_rate': HERO_TOWER_RANGE,
        'tower_range': HERO_TOWER_RANGE,

        # Hero speed - by itself
        'hero_speed': SPEED_RANGE,
    }

    @lru_cache(maxsize=100000)
    def normalize_stat(self, stat_name: str, value: int) -> float:
        """
        Normalize a stat value to 0-1 scale using grouped ranges.

        Args:
            stat_name: Name of the stat
            value: Raw stat value

        Returns:
            Normalized value between 0.0 and 1.0
        """
        if stat_name not in self.STAT_GROUPS:
            return 0.0

        min_val, max_val = self.STAT_GROUPS[stat_name]
        if max_val == min_val:
            return 0.0

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))  # Clamp to [0, 1]
