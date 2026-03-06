"""Main recommendation engine for armor set optimization."""

import logging
import math
import time
import heapq
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Tuple
from itertools import product

from armor_select.shared.constraint_manager import ConstraintManager
from armor_select.shared.stat_normalizer import StatNormalizer

logger = logging.getLogger(__name__)


class TooManyCombinationsError(Exception):
    """Raised when the number of combinations to evaluate exceeds the limit."""
    pass


class TaskCancelledError(Exception):
    """Raised when the current task has been cancelled (e.g. a new task was started)."""
    pass


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

    @lru_cache(maxsize=10000)
    def _get_cached_piece_stats(self, stat_values_tuple: Tuple[int, ...]) -> Dict[str, int]:
        """
        Cached version of stat extraction that works with stat values tuple.

        Args:
            stat_values_tuple: Tuple of stat values in STAT_TYPES order

        Returns:
            Dictionary of stat values
        """
        return dict(zip(self.STAT_TYPES, stat_values_tuple))

    def get_piece_stats(self, piece: Dict) -> Dict[str, int]:
        """
        Extract stat values from a piece as a dictionary.

        Args:
            piece: Armor piece dictionary

        Returns:
            Dictionary of stat values (defaults to 0 for missing stats)
        """
        # Extract stat values as tuple for caching
        stat_values = tuple(
            int(piece.get(stat, 0)) if isinstance(piece.get(stat, 0), (int, float)) else 0
            for stat in self.STAT_TYPES
        )
        return self._get_cached_piece_stats(stat_values)

    def is_dominated(self, piece_a: Dict, piece_b: Dict) -> bool:
        """
        Check if piece_a is strictly dominated by piece_b.

        Piece A is dominated by Piece B if:
        - For all stats, B >= A (B is not worse in any stat)
        - For at least one stat, B > A (B is strictly better in at least one stat)

        Args:
            piece_a: First armor piece to compare
            piece_b: Second armor piece to compare

        Returns:
            True if piece_a is dominated by piece_b, False otherwise
        """
        stats_a = self.get_piece_stats(piece_a)
        stats_b = self.get_piece_stats(piece_b)

        all_better_or_equal = True
        at_least_one_better = False

        for stat in self.STAT_TYPES:
            val_a = stats_a.get(stat, 0)
            val_b = stats_b.get(stat, 0)

            if val_b < val_a:
                # B is worse in this stat, so B doesn't dominate A
                all_better_or_equal = False
                break
            elif val_b > val_a:
                # B is strictly better in this stat
                at_least_one_better = True

        return all_better_or_equal and at_least_one_better

    def filter_dominated_pieces(self, pieces: List[Dict]) -> List[Dict]:
        """
        Filter out pieces that are strictly dominated by other pieces.

        For a group of pieces of the same armor_set and armor_type,
        remove any piece that is strictly worse than another piece in all stats.

        Args:
            pieces: List of armor pieces (should be same armor_set and armor_type)

        Returns:
            Filtered list with dominated pieces removed
        """
        if len(pieces) <= 1:
            return pieces

        # Track which pieces are dominated
        dominated_indices = set()

        # Compare all pairs of pieces
        for i in range(len(pieces)):
            if i in dominated_indices:
                continue
            for j in range(i + 1, len(pieces)):
                if j in dominated_indices:
                    continue

                # Check if piece_i is dominated by piece_j
                if self.is_dominated(pieces[i], pieces[j]):
                    dominated_indices.add(i)
                    break
                # Check if piece_j is dominated by piece_i
                elif self.is_dominated(pieces[j], pieces[i]):
                    dominated_indices.add(j)

        # Return only non-dominated pieces
        filtered = [pieces[i] for i in range(len(pieces)) if i not in dominated_indices]
        return filtered

    def can_set_satisfy_constraints(
        self,
        pieces_by_armor_type: Dict[str, List[Dict]],
        constraints: Dict[str, int]
    ) -> bool:
        """
        Check if a set can possibly satisfy all constraints.

        Calculates the maximum possible stats by taking the best piece for each
        stat across all armor types. If the maximum possible stats cannot satisfy
        all constraints, no combination from this set can.

        Args:
            pieces_by_armor_type: Dictionary mapping armor types to lists of pieces
            constraints: Dictionary mapping stat names to minimum required values

        Returns:
            True if the set can possibly satisfy all constraints, False otherwise
        """
        if not constraints:
            return True

        # Calculate maximum possible stats by taking best piece for each stat
        max_possible_stats = {stat: 0 for stat in self.STAT_TYPES}

        for armor_type, pieces in pieces_by_armor_type.items():
            for stat in self.STAT_TYPES:
                max_for_type = max((p.get(stat, 0) for p in pieces), default=0)
                max_possible_stats[stat] += max_for_type

        # Check if max possible stats can satisfy all constraints
        for stat, min_val in constraints.items():
            if max_possible_stats.get(stat, 0) < min_val:
                return False

        return True

    def can_satisfy_constraints_from_here(
        self,
        current_stats: Dict[str, int],
        remaining_armor_types: List[str],
        pieces_by_armor_type: Dict[str, List[Dict]],
        constraints: Dict[str, int]
    ) -> bool:
        """
        Check if constraints can still be satisfied from a partial combination.

        Calculates the maximum possible stats from remaining armor types and checks
        if current stats plus max remaining can satisfy all constraints.

        Args:
            current_stats: Stats from pieces already selected
            remaining_armor_types: List of armor types not yet selected
            pieces_by_armor_type: Dictionary mapping armor types to lists of pieces
            constraints: Dictionary mapping stat names to minimum required values

        Returns:
            True if constraints can still be satisfied, False otherwise
        """
        if not constraints:
            return True

        # Calculate max possible stats from remaining pieces
        max_remaining = {stat: 0 for stat in self.STAT_TYPES}

        for armor_type in remaining_armor_types:
            pieces = pieces_by_armor_type.get(armor_type, [])
            for stat in self.STAT_TYPES:
                max_for_type = max((p.get(stat, 0) for p in pieces), default=0)
                max_remaining[stat] += max_for_type

        # Check if current + max remaining can satisfy constraints
        for stat, min_val in constraints.items():
            total_possible = current_stats.get(stat, 0) + max_remaining.get(stat, 0)
            if total_possible < min_val:
                return False

        return True

    def sort_pieces_by_quality(
        self,
        pieces_by_armor_type: Dict[str, List[Dict]],
        weights: Dict[str, float]
    ) -> Dict[str, List[Dict]]:
        """
        Sort pieces by individual weighted score contribution for each armor type.

        This enables ordered exploration where best combinations are evaluated first.

        Args:
            pieces_by_armor_type: Dictionary mapping armor types to lists of pieces
            weights: Dictionary mapping stat names to weights

        Returns:
            Dictionary with pieces sorted by quality (best first) for each armor type
        """
        sorted_pieces = {}

        for armor_type, pieces in pieces_by_armor_type.items():
            # Score each piece individually
            scored = []
            for piece in pieces:
                stats = self.get_piece_stats(piece)
                score = self.calculate_score(stats, weights)
                scored.append((score, piece))

            # Sort by score (best first)
            scored.sort(reverse=True, key=lambda x: x[0])
            sorted_pieces[armor_type] = [p for _, p in scored]

        return sorted_pieces

    def depth_first_recommendations(
        self,
        pieces_by_armor_type: Dict[str, List[Dict]],
        weights: Dict[str, float],
        constraints: Dict[str, int],
        limit: int = 10,
        timeout_seconds: Optional[float] = None,
        progress_callback: Optional[Callable[[int, int, Optional[List[Dict]]], None]] = None,
        check_cancelled: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, List[Dict], Dict[str, int]]]:
        """
        Evaluate combinations depth-first with priority queue.

        Uses ordered exploration (sorted pieces) to evaluate best combinations first.
        Maintains a priority queue of top N results. Runs to completion unless
        timeout_seconds is set or check_cancelled returns True.

        Args:
            pieces_by_armor_type: Dictionary mapping armor types to lists of pieces
            weights: Dictionary mapping stat names to weights
            constraints: Dictionary mapping stat names to minimum values
            limit: Maximum number of results to return
            timeout_seconds: Maximum time to spend evaluating (None = run to completion)
            progress_callback: Optional callback (evaluated, total_planned, partial_results)
                called periodically; partial_results is current top-N formatted or None.
            check_cancelled: Optional callback; if it returns True, stop and return best-so-far

        Returns:
            List of tuples (score, pieces_list, stats_dict) sorted by score (best first)
        """
        # Sort pieces by quality for ordered exploration
        sorted_pieces = self.sort_pieces_by_quality(pieces_by_armor_type, weights)

        # Calculate total planned combinations
        total_planned = 1
        for armor_type in sorted_pieces.keys():
            total_planned *= len(sorted_pieces[armor_type])

        logger.info(f"Total combinations to evaluate: {total_planned}")

        # Initialize priority queue (min-heap) for top N results
        # Store as (score, counter, pieces, stats) where lower score = lower priority
        # We want to keep the highest scores, so we use a min-heap and compare scores
        heap = []
        start_time = time.time()
        evaluated = 0
        last_log_time = start_time
        last_log_count = 0
        last_callback_time = start_time
        counter = 0  # Tie-breaker for heap comparison

        # Iterate through combinations using sorted pieces
        armor_types = list(sorted_pieces.keys())
        for combo in product(*[sorted_pieces[at] for at in armor_types]):
            # Optional timeout
            if timeout_seconds is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    remaining = total_planned - evaluated
                    logger.info(
                        f"Timeout reached after {elapsed:.2f}s. "
                        f"Evaluated {evaluated}/{total_planned} combinations. "
                        f"Remaining: {remaining}. Returning best results found so far."
                    )
                    break

            evaluated += 1

            # Progress callback periodically (every 1000 evaluations or every 0.5s)
            if progress_callback is not None:
                current_time = time.time()
                if (evaluated - last_log_count >= 1000) or (current_time - last_callback_time >= 0.5):
                    partial = None
                    if heap:
                        sorted_heap = sorted(heap, key=lambda x: -x[0])
                        partial = [
                            self._format_scored_set(combo_list, stats, score, idx)
                            for idx, (score, _, combo_list, stats) in enumerate(sorted_heap[:limit])
                        ]
                    progress_callback(evaluated, total_planned, partial)
                    last_callback_time = current_time

            # Check for cancellation
            if check_cancelled is not None and check_cancelled():
                logger.info(f"Task cancelled after {evaluated}/{total_planned} combinations")
                raise TaskCancelledError()

            # Log progress periodically (every 10000 evaluations or every 10 seconds)
            current_time = time.time()
            if (evaluated - last_log_count >= 10000) or (current_time - last_log_time >= 10.0):
                logger.info(f"Evaluated {evaluated}/{total_planned} combinations")
                last_log_time = current_time
                last_log_count = evaluated

            # Aggregate stats
            combo_list = list(combo)
            stats = self.aggregate_stats(combo_list)

            # Check hard constraints
            violations = self.constraint_manager.violates_hard_constraints(stats)
            if violations:
                continue  # Skip sets that violate constraints

            # Calculate score
            score = self.calculate_score(stats, weights)

            # Maintain heap of size limit
            # Use counter as tie-breaker to ensure tuple comparison works
            counter += 1
            if len(heap) < limit:
                heapq.heappush(heap, (score, counter, combo_list, stats))
            elif score > heap[0][0]:
                heapq.heapreplace(heap, (score, counter, combo_list, stats))

        # Final progress callback (include partial results if any)
        if progress_callback is not None:
            partial = None
            if heap:
                sorted_heap = sorted(heap, key=lambda x: -x[0])
                partial = [
                    self._format_scored_set(combo_list, stats, score, idx)
                    for idx, (score, _, combo_list, stats) in enumerate(sorted_heap[:limit])
                ]
            progress_callback(evaluated, total_planned, partial)

        # Return top results sorted by score (best first)
        results = [(score, pieces, stats) for score, _, pieces, stats in heap]
        results.sort(reverse=True, key=lambda x: x[0])
        return results

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

    def _format_scored_set(
        self,
        armor_set: List[Dict],
        aggregated_stats: Dict[str, int],
        score: float,
        idx: int
    ) -> Dict:
        """Format a single (armor_set, stats, score) as a recommendation dict."""
        set_id = self.generate_set_id(armor_set, idx)
        formatted_pieces = []
        for piece in armor_set:
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
        return {
            'set_id': set_id,
            'pieces': formatted_pieces,
            'current_stats': aggregated_stats,
            'upgraded_stats': aggregated_stats.copy(),
            'effective_stats': aggregated_stats.copy(),
            'wasted_points': {stat: 0 for stat in self.STAT_TYPES},
            'score': score,
            'potential_score': 0.0,
            'flexibility_score': 0.0,
        }

    def get_recommendations(
        self,
        weights: Dict[str, float],
        constraints: Dict[str, int],
        limit: int = 10,
        progress_callback: Optional[Callable[[int, int, Optional[List[Dict]]], None]] = None,
        check_cancelled: Optional[Callable[[], bool]] = None
    ) -> List[Dict]:
        """
        Get top armor set recommendations.

        Args:
            weights: Dictionary mapping stat names to weights
            constraints: Dictionary mapping stat names to minimum values
            limit: Maximum number of recommendations to return
            progress_callback: Optional callback (evaluated, total_planned, partial_results)
                called after each set completes; partial_results is top-N list so far.
            check_cancelled: Optional callback; if it returns True, stop and return best-so-far

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

        # Filter out dominated pieces to reduce combination count
        original_piece_count = sum(len(pieces) for pieces in sets_by_type.values())
        filtered_piece_count = 0

        for set_type, pieces in sets_by_type.items():
            pieces_by_armor_type: Dict[str, List[Dict]] = {}
            for piece in pieces:
                armor_type = piece.get('armor_type')
                if armor_type:
                    if armor_type not in pieces_by_armor_type:
                        pieces_by_armor_type[armor_type] = []
                    pieces_by_armor_type[armor_type].append(piece)

            filtered_by_armor_type: Dict[str, List[Dict]] = {}
            for armor_type, armor_pieces in pieces_by_armor_type.items():
                filtered_pieces = self.filter_dominated_pieces(armor_pieces)
                filtered_by_armor_type[armor_type] = filtered_pieces
                filtered_piece_count += len(filtered_pieces)

            sets_by_type[set_type] = []
            for armor_type, filtered_pieces in filtered_by_armor_type.items():
                sets_by_type[set_type].extend(filtered_pieces)

        removed_count = original_piece_count - filtered_piece_count
        if removed_count > 0:
            logger.info(
                f"Filtered out {removed_count} dominated pieces "
                f"({original_piece_count} -> {filtered_piece_count})"
            )

        # Build list of (set_type, pieces_by_armor_type) we will process and total_planned per set
        sets_to_process: List[Tuple[str, Dict[str, List[Dict]]]] = []
        for set_type, pieces in sets_by_type.items():
            pieces_by_armor_type = {}
            for piece in pieces:
                armor_type = piece.get('armor_type')
                if armor_type:
                    if armor_type not in pieces_by_armor_type:
                        pieces_by_armor_type[armor_type] = []
                    pieces_by_armor_type[armor_type].append(piece)
            if len(pieces_by_armor_type) != 7:
                continue
            if not self.can_set_satisfy_constraints(pieces_by_armor_type, constraints):
                logger.info(
                    f"Skipping set '{set_type}': cannot satisfy constraints even with best pieces"
                )
                continue
            sets_to_process.append((set_type, pieces_by_armor_type))

        total_planned_global = 0
        for _set_type, pbat in sets_to_process:
            n = 1
            for armor_type in pbat:
                n *= len(pbat[armor_type])
            total_planned_global += n

        # Process each set with optimizations
        all_scored_sets: List[Dict] = []
        evaluated_so_far = 0

        for set_type, pieces_by_armor_type in sets_to_process:
            if check_cancelled is not None and check_cancelled():
                logger.info("Task cancelled between sets")
                raise TaskCancelledError()

            total_this_set = 1
            for armor_type in pieces_by_armor_type:
                total_this_set *= len(pieces_by_armor_type[armor_type])

            def make_progress_callback():
                _evaluated_before = evaluated_so_far
                _total_global = total_planned_global
                def cb(
                    evaluated_this: int,
                    _total_this: int,
                    partial_list: Optional[List[Dict]] = None,
                ) -> None:
                    if progress_callback is not None:
                        progress_callback(
                            _evaluated_before + evaluated_this,
                            _total_global,
                            partial_list,
                        )
                return cb

            # Run to completion (no timeout)
            results = self.depth_first_recommendations(
                pieces_by_armor_type,
                weights,
                constraints,
                limit=limit,
                timeout_seconds=None,
                progress_callback=make_progress_callback() if progress_callback else None,
                check_cancelled=check_cancelled
            )

            # Format results for this set
            for idx, (score, armor_set, aggregated_stats) in enumerate(results):
                all_scored_sets.append(
                    self._format_scored_set(armor_set, aggregated_stats, score, idx)
                )

            evaluated_so_far += total_this_set

            # Merge and take top N, then report partial results
            all_scored_sets.sort(key=lambda x: x['score'], reverse=True)
            partial = all_scored_sets[:limit]
            if progress_callback is not None:
                progress_callback(evaluated_so_far, total_planned_global, partial)

        # Sort by score (descending) and return top N
        all_scored_sets.sort(key=lambda x: x['score'], reverse=True)
        return all_scored_sets[:limit]
