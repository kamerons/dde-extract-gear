"""Load and validate armor data from JSON file."""

import json
import os
from pathlib import Path
from typing import Dict, List

from armor_select.shared.models import ArmorPiece


class DataLoader:
    """Loads and validates armor data from JSON file."""

    def __init__(self, data_file: str = "data/collected.json"):
        """
        Initialize data loader.

        Args:
            data_file: Path to JSON file containing armor data
        """
        self.data_file = data_file
        self.inventory: List[Dict] = []

    def load(self) -> List[Dict]:
        """
        Load armor data from JSON file.

        Returns:
            List of armor piece dictionaries

        Raises:
            FileNotFoundError: If data file doesn't exist
            ValueError: If data file is invalid or empty
        """
        # Get absolute path relative to repo root
        repo_root = Path(__file__).parent.parent.parent
        data_path = repo_root / self.data_file

        if not data_path.exists():
            raise FileNotFoundError(
                f"Armor data file not found: {data_path}. "
                f"Please ensure {self.data_file} exists."
            )

        with open(data_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in {data_path}: {e}"
                ) from e

        if not isinstance(data, list):
            raise ValueError(
                f"Expected list of armor pieces, got {type(data).__name__}"
            )

        if len(data) == 0:
            raise ValueError(
                f"Armor data file is empty: {data_path}"
            )

        # Validate each piece has required fields
        validated_data = []
        for i, piece in enumerate(data):
            if not isinstance(piece, dict):
                raise ValueError(
                    f"Item {i} is not a dictionary: {type(piece).__name__}"
                )

            if 'armor_set' not in piece:
                raise ValueError(
                    f"Item {i} missing required field 'armor_set'"
                )

            if 'armor_type' not in piece:
                raise ValueError(
                    f"Item {i} missing required field 'armor_type'"
                )

            # Generate ID if missing
            if 'id' not in piece:
                piece['id'] = f"piece_{i}"

            validated_data.append(piece)

        self.inventory = validated_data
        return validated_data

    def group_by_set_type(self) -> Dict[str, List[Dict]]:
        """
        Group armor pieces by set type.

        Returns:
            Dictionary mapping set type to list of pieces
        """
        sets_by_type: Dict[str, List[Dict]] = {}
        for piece in self.inventory:
            set_type = piece.get('armor_set')
            if set_type:
                if set_type not in sets_by_type:
                    sets_by_type[set_type] = []
                sets_by_type[set_type].append(piece)
        return sets_by_type

    def generate_complete_sets(self) -> List[List[Dict]]:
        """
        Generate all possible complete sets (4 pieces from same set).

        Returns:
            List of complete sets, where each set is a list of 4 armor pieces
        """
        sets_by_type = self.group_by_set_type()
        complete_sets = []

        for set_type, pieces in sets_by_type.items():
            if len(pieces) >= 4:
                # Generate all combinations of 4 pieces from this set
                # For now, use itertools.combinations
                from itertools import combinations
                for combo in combinations(pieces, 4):
                    complete_sets.append(list(combo))

        return complete_sets
