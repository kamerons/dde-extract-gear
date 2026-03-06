"""Main recommendation engine for armor set optimization."""

from typing import Dict, List
from itertools import combinations

from armor_select.backend.constraint_manager import ConstraintManager
from armor_select.backend.stat_normalizer import StatNormalizer


class RecommendationEngine:
    """Main engine for generating armor set recommendations."""

    # Stat types that should be aggregated
    STAT_TYPES = [
        'base', 'fire', 'electric', 'poison',
        'hero_hp', 'hero_dmg', 'hero_rate', 'hero_speed',
        'offense', 'defense',
        'tower_hp', 'tower_dmg', 'tower_rate', 'tower_range'
    ]

    def __init__(self, inventory: List[Dict]):
        """
        Initialize recommendation engine.

        Args:
            inventory: List of armor piece dictionaries
        """
        self.inventory = inventory
        self.stat_normalizer = StatNormalizer()
        self.constraint_manager = ConstraintManager()

    def aggregate_stats(self, pieces: List[Dict]) -> Dict[str, int]:
        """
        Aggregate stats from multiple armor pieces.

        Args:
            pieces: List of armor piece dictionaries

        Returns:
            Dictionary of aggregated stat values
        """
        aggregated = {stat: 0 for stat in self.STAT_TYPES}

        for piece in pieces:
            for stat in self.STAT_TYPES:
                # Get stat value, default to 0 if missing
                stat_value = piece.get(stat, 0)
                if isinstance(stat_value, (int, float)):
                    aggregated[stat] += int(stat_value)

        return aggregated

    def calculate_score(
        self,
        stats: Dict[str, int],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate weighted score for a set of stats.

        Args:
            stats: Dictionary of stat values
            weights: Dictionary of stat weights

        Returns:
            Weighted score
        """
        if not weights:
            return 0.0

        score = 0.0
        for stat, value in stats.items():
            if stat in weights and weights[stat] > 0:
                normalized = self.stat_normalizer.normalize_stat(stat, value)
                score += normalized * weights[stat]

        return score

    def generate_set_id(self, pieces: List[Dict], index: int) -> str:
        """
        Generate unique ID for a complete set.

        Args:
            pieces: List of armor pieces in the set
            index: Index of this set combination

        Returns:
            Unique set ID
        """
        set_type = pieces[0].get('armor_set', 'unknown')
        # Create ID from set type and piece IDs
        piece_ids = '_'.join(sorted([p.get('id', '') for p in pieces]))
        return f"{set_type.lower().replace(' ', '_')}_{index}_{hash(piece_ids) % 10000}"

    def get_recommendations(
        self,
        weights: Dict[str, float],
        constraints: Dict[str, int],
        limit: int = 10
    ) -> List[Dict]:
        """
        Get top armor set recommendations.

        Args:
            weights: Dictionary mapping stat names to weights
            constraints: Dictionary mapping stat names to minimum values
            limit: Maximum number of recommendations to return

        Returns:
            List of recommendation dictionaries
        """
        # Set constraints
        self.constraint_manager.set_min_constraints(constraints)

        # Group inventory by set type
        sets_by_type: Dict[str, List[Dict]] = {}
        for piece in self.inventory:
            set_type = piece.get('armor_set')
            if set_type:
                if set_type not in sets_by_type:
                    sets_by_type[set_type] = []
                sets_by_type[set_type].append(piece)

        # Generate complete sets (4 pieces from same set)
        complete_sets = []
        for set_type, pieces in sets_by_type.items():
            if len(pieces) >= 4:
                # Generate all combinations of 4 pieces
                for combo in combinations(pieces, 4):
                    complete_sets.append(list(combo))

        if not complete_sets:
            return []

        # Score all sets
        scored_sets = []
        for idx, armor_set in enumerate(complete_sets):
            # Aggregate stats
            aggregated_stats = self.aggregate_stats(armor_set)

            # Check hard constraints
            violations = self.constraint_manager.violates_hard_constraints(
                aggregated_stats
            )
            if violations:
                continue  # Skip sets that violate constraints

            # Calculate score
            score = self.calculate_score(aggregated_stats, weights)

            # Generate set ID
            set_id = self.generate_set_id(armor_set, idx)

            # Format pieces for response
            formatted_pieces = []
            for piece in armor_set:
                # Extract stats from piece
                piece_stats = {
                    stat: piece.get(stat, 0)
                    for stat in self.STAT_TYPES
                    if isinstance(piece.get(stat, 0), (int, float))
                }
                formatted_pieces.append({
                    'armor_set': piece.get('armor_set', ''),
                    'armor_type': piece.get('armor_type', ''),
                    'current_level': piece.get('current_level', 1),
                    'max_level': piece.get('max_level', 16),
                    'stats': piece_stats
                })

            # For Phase 1, use same stats for all stat fields
            # (upgraded_stats, effective_stats, wasted_points will be
            # implemented in Phase 2/3)
            scored_sets.append({
                'set_id': set_id,
                'pieces': formatted_pieces,
                'current_stats': aggregated_stats,
                'upgraded_stats': aggregated_stats.copy(),  # Placeholder
                'effective_stats': aggregated_stats.copy(),  # Placeholder
                'wasted_points': {stat: 0 for stat in self.STAT_TYPES},  # Placeholder
                'score': score,
                'potential_score': 0.0,  # Placeholder for Phase 3
                'flexibility_score': 0.0,  # Placeholder for Phase 3
            })

        # Sort by score (descending)
        scored_sets.sort(key=lambda x: x['score'], reverse=True)

        # Return top N
        return scored_sets[:limit]
