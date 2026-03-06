"""Processor for recommendation tasks."""

import logging
from typing import Callable, Dict, List, Optional

from armor_select.shared.data_loader import DataLoader
from armor_select.shared.recommendation_engine import (
    RecommendationEngine,
    TooManyCombinationsError,
    TaskCancelledError,
)

logger = logging.getLogger(__name__)


class RecommendationProcessor:
    """Processes recommendation calculation tasks."""

    def __init__(self, data_file: str = "data/collected.json"):
        """
        Initialize recommendation processor.

        Args:
            data_file: Path to JSON file containing armor data
        """
        self.data_file = data_file
        self._inventory: List[Dict] = None
        self._engine: RecommendationEngine = None

    def _load_inventory(self) -> None:
        """Load inventory if not already loaded."""
        if self._inventory is None:
            loader = DataLoader(self.data_file)
            self._inventory = loader.load()
            self._engine = RecommendationEngine(self._inventory)
            logger.info(f"Loaded {len(self._inventory)} armor pieces")

    def process(
        self,
        weights: Dict[str, float],
        constraints: Dict[str, int],
        limit: int = 10,
        progress_callback: Optional[Callable[[int, int, Optional[Dict]], None]] = None,
        check_cancelled: Optional[Callable[[], bool]] = None
    ) -> Dict:
        """
        Process a recommendation task.

        Args:
            weights: Dictionary mapping stat names to weights
            constraints: Dictionary mapping stat names to minimum values
            limit: Maximum number of recommendations to return
            progress_callback: Optional callback (evaluated, total_planned, partial_results).
                partial_results is {"recommendations": [...], "count": N} or None.
            check_cancelled: Optional callback; if it returns True, abort and raise TaskCancelledError.

        Returns:
            Dictionary with recommendations data

        Raises:
            TooManyCombinationsError: If too many combinations to evaluate
            TaskCancelledError: If the task was cancelled
            Exception: For other processing errors
        """
        self._load_inventory()

        logger.info(f"Processing recommendation: weights={weights}, constraints={constraints}, limit={limit}")

        def engine_progress_callback(
            evaluated: int,
            total_planned: int,
            partial_list: Optional[List[Dict]]
        ) -> None:
            if progress_callback is None:
                return
            partial_dict: Optional[Dict] = None
            if partial_list is not None:
                partial_dict = {
                    "recommendations": partial_list,
                    "count": len(partial_list)
                }
            progress_callback(evaluated, total_planned, partial_dict)

        try:
            recommendations_data = self._engine.get_recommendations(
                weights=weights,
                constraints=constraints,
                limit=limit,
                progress_callback=engine_progress_callback,
                check_cancelled=check_cancelled
            )

            # Format response
            return {
                "recommendations": recommendations_data,
                "count": len(recommendations_data)
            }
        except TooManyCombinationsError as e:
            logger.error(f"Too many combinations: {e}")
            raise
        except TaskCancelledError:
            logger.info("Recommendation task was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error processing recommendations: {e}")
            raise
