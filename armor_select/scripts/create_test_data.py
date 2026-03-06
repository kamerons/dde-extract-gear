"""Create a fake collected.json file for testing."""

import json
import random
from pathlib import Path

from extract_gear.constants import ARMOR_TYPES, SET_TYPES


def create_test_collected_json(
    output_path: str = "data/collected.json",
    num_pieces: int = 1000,
    seed: int = None
):
    """
    Create a fake collected.json file with randomly generated test armor pieces.

    Args:
        output_path: Path to output JSON file (relative to repo root)
        num_pieces: Total number of armor pieces to generate (default 1000)
        seed: Random seed for reproducibility (optional)
    """
    if seed is not None:
        random.seed(seed)

    # Get absolute path relative to repo root
    # From armor_select/scripts/create_test_data.py:
    # .parent = armor_select/scripts
    # .parent.parent = armor_select
    # .parent.parent.parent = repo root (dde-extract-gear)
    repo_root = Path(__file__).parent.parent.parent
    data_path = repo_root / output_path

    # Ensure data directory exists
    data_path.parent.mkdir(parents=True, exist_ok=True)

    # Use constants from shared module
    armor_sets = SET_TYPES
    armor_types = ARMOR_TYPES

    # Stat ranges based on normalization groups
    # Base resistance: 0-100
    # Fire/Electric/Poison: 0-50
    # Hero/Tower stats (except speed): 0-50
    # Hero speed: 0-100

    # All 14 possible stats
    ALL_STATS = [
        "base",
        "fire",
        "electric",
        "poison",
        "hero_hp",
        "hero_dmg",
        "hero_rate",
        "hero_speed",
        "offense",
        "defense",
        "tower_hp",
        "tower_dmg",
        "tower_rate",
        "tower_range",
    ]

    def generate_random_stats():
        """
        Generate exactly 8 random stats for an armor piece.

        Requirements:
        - Always includes 'base'
        - Always includes exactly one of fire/electric/poison (one more defense type)
        - Randomly selects 6 more stats from the remaining 11 stats (excluding other resistances)
        """
        stats = {}

        # Always include base (0-100)
        stats["base"] = random.randint(50, 100)

        # Always include exactly one resistance type (fire/electric/poison) (0-50)
        resistance_stats = ["fire", "electric", "poison"]
        selected_resistance = random.choice(resistance_stats)
        stats[selected_resistance] = random.randint(5, 50)

        # Select 6 more stats from the remaining stats
        # Exclude base and all resistance types (we already have one)
        remaining_stats = [
            stat for stat in ALL_STATS
            if stat != "base" and stat not in resistance_stats
        ]
        selected_additional = random.sample(remaining_stats, 6)

        # Generate values for the 6 additional stats
        for stat in selected_additional:
            if stat == "hero_speed":
                # Hero speed uses 0-100 range
                stats[stat] = random.randint(1, 100)
            else:
                # All other stats (hero/tower/offense/defense) use 0-50 range
                stats[stat] = random.randint(5, 50)

        return stats

    # Generate armor pieces - completely random, no grouping
    armor_pieces = []

    for piece_counter in range(1, num_pieces + 1):
        # Randomly select armor set and type for each piece
        set_name = random.choice(armor_sets)
        armor_type = random.choice(armor_types)

        piece = {
            "id": f"test_piece_{piece_counter}",
            "armor_set": set_name,
            "armor_type": armor_type,
            "current_level": random.randint(1, 5),
            "max_level": 16,
        }

        # Add random stats
        piece.update(generate_random_stats())

        armor_pieces.append(piece)

    # Write to file
    with open(data_path, 'w') as f:
        json.dump(armor_pieces, f, indent=2)

    # Count sets
    sets_by_name = {}
    for piece in armor_pieces:
        set_name = piece["armor_set"]
        sets_by_name[set_name] = sets_by_name.get(set_name, 0) + 1

    print(f"Created test data file: {data_path}")
    print(f"Generated {len(armor_pieces)} armor pieces")
    print(f"Sets generated: {len(sets_by_name)}")
    for set_name, count in sets_by_name.items():
        print(f"  - {set_name}: {count} pieces")


if __name__ == "__main__":
    create_test_collected_json()
