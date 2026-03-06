# Armor Selection System Architecture

## Overview

The Armor Selection System is a React + Python server application that helps users find the best armor combinations from extracted gear data. The system provides intelligent recommendations based on user preferences, handles upgrades, considers future-proofing, and supports incremental changes to existing armor sets.

## Core Requirements

### Key Constraints
- **Complete Sets Only**: Armor must form a complete set (4 pieces from the same `armor_set`) to be considered, as set bonuses are significant. Note: There are 7 armor types available, but only 4 are needed for a complete set.
- **No Neural Networks**: Preference learning must be lightweight and instant (no training time)
- **No LLM Integration**: All feedback is structured (buttons, no text input)
- **Reactive Constraint Discovery**: Users discover constraints as they see recommendations, not upfront

### Key Features
1. **Multi-Objective Optimization**: Weighted scoring of stats based on user preferences
2. **Soft Caps**: Stats become less valuable after thresholds (diminishing returns)
3. **Upgrade Support**: Armor upgrades boost the highest stat by 10%
4. **Future-Proofing**: Considers potential value as better armor becomes available
5. **Incremental Changes**: Evaluates partial replacements to existing sets
6. **Reactive Feedback**: Users provide feedback via thumbs up/down + stat adjustments

## System Architecture

### Directory Structure

```
armor_select/
├── backend/
│   ├── recommendation_engine.py    # Main optimization logic
│   ├── constraint_manager.py        # Hard constraints & soft caps
│   ├── upgrade_calculator.py        # Upgrade calculations
│   ├── future_proof_scorer.py      # Potential value scoring
│   ├── incremental_evaluator.py     # Partial replacement evaluation
│   ├── preference_adjuster.py       # Lightweight preference learning
│   ├── stat_normalizer.py          # Stat normalization by type
│   ├── feedback_handler.py          # Process user feedback
│   ├── data_loader.py              # Load JSON armor data
│   └── api.py                      # FastAPI/Flask endpoints
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── RecommendationCard.tsx      # Display recommended set
│   │   │   ├── StatComparison.tsx          # Show stat differences
│   │   │   ├── FeedbackPanel.tsx           # Collect user feedback
│   │   │   ├── PreferenceEditor.tsx        # Manual weight adjustment
│   │   │   ├── ConstraintEditor.tsx        # Set min/max constraints
│   │   │   ├── SoftCapEditor.tsx           # Set soft cap thresholds
│   │   │   ├── UpgradePreview.tsx          # Show upgraded stats
│   │   │   ├── IncrementalChangeView.tsx   # Show partial replacements
│   │   │   └── WasteIndicator.tsx          # Highlight wasted points
│   │   ├── hooks/
│   │   │   └── useRecommendations.ts      # API integration
│   │   └── App.tsx
│   └── package.json
└── ARCHITECTURE.md                  # This file
```

## Data Structures

### Armor Piece
```python
armor_piece = {
    'id': 'unique_id',                    # Unique identifier
    'armor_set': 'Chain Armor Set',       # Set type (must match for complete set)
    'armor_type': 'shoulder_pad',         # Piece type (shoulder_pad, mask, hat, greaves, shield, bracer, belt)
    'current_level': 1,                   # Current upgrade level
    'max_level': 16,                      # Maximum upgrade level
    'defense': 450,                       # Stat values (vary by piece)
    'attack': 320,
    'hero_speed': 15,
    'hero_hp': 1200,
    'hero_dmg': 800,
    'hero_rate': 600,
    'offense': 500,
    'tower_hp': 2000,
    'tower_dmg': 1000,
    'tower_rate': 800,
    'tower_range': 50,
    'base': 300,
    'fire': 200,
    'electric': 150,
    'poison': 100,
    # ... other stats
}
```

### Complete Armor Set
```python
complete_set = {
    'id': 'chain_set_001',
    'pieces': [piece1, piece2, piece3, piece4],  # 4 pieces from same set
    'set_type': 'Chain Armor Set',
    'aggregated_stats': {                        # Sum of all 4 pieces
        'defense': 1800,
        'attack': 1280,
        'hero_speed': 60,
        # ...
    }
}
```

### Recommendation Result
```python
recommendation = {
    'set_id': 'chain_set_001',
    'pieces': [piece1, piece2, piece3, piece4],
    'current_stats': {...},              # Current aggregated stats
    'upgraded_stats': {...},            # Stats after upgrades (10% boost to highest stat per piece)
    'effective_stats': {...},            # After soft caps applied
    'wasted_points': {...},              # Points wasted over soft caps
    'score': 0.85,                       # Weighted score
    'potential_score': 0.12,             # Future improvement potential
    'flexibility_score': 0.08,          # How many alternatives exist
    'improvements': [                    # For incremental mode
        {
            'type': 'single_replacement',
            'position': 0,
            'improvement': 0.15,
            'old_piece': {...},
            'new_piece': {...}
        }
    ]
}
```

## Core Components

### 1. Stat Normalizer

Normalizes stats to 0-1 scale since different stats have different ranges (e.g., Speed caps at ~100, Attack can be 5000+).

```python
class StatNormalizer:
    STAT_RANGES = {
        'hero_speed': (0, 100),      # Hard cap mentioned
        'hero_hp': (0, 10000),
        'hero_dmg': (0, 5000),
        'hero_rate': (0, 5000),
        'defense': (0, 5000),
        'offense': (0, 5000),
        'tower_hp': (0, 10000),
        'tower_dmg': (0, 5000),
        'tower_rate': (0, 5000),
        'tower_range': (0, 200),
        'base': (0, 5000),
        'fire': (0, 5000),
        'electric': (0, 5000),
        'poison': (0, 5000),
    }

    def normalize_stat(self, stat_name, value):
        """Normalize to 0-1 scale"""
        if stat_name not in self.STAT_RANGES:
            return 0.0

        min_val, max_val = self.STAT_RANGES[stat_name]
        if max_val == min_val:
            return 0.0

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))  # Clamp to [0, 1]
```

### 2. Constraint Manager

Handles both hard constraints (minimums) and soft caps (diminishing returns).

**Hard Constraints**: Must have at least X (e.g., "need at least 800 attack")
**Soft Caps**: Value diminishes after threshold (e.g., "have 120 speed, but 100 is enough")

```python
class EnhancedConstraintManager:
    def __init__(self):
        self.min_constraints = {}  # Hard: must have at least X
        self.soft_caps = {}        # Soft: value diminishes after X

    def add_min_constraint(self, stat_name, value):
        """User discovers they need at least X"""
        self.min_constraints[stat_name] = value

    def add_soft_cap(self, stat_name, threshold, penalty_rate=0.5):
        """
        User discovers stat becomes less valuable after threshold
        penalty_rate: 0.0 = no value after threshold, 1.0 = full value
        """
        self.soft_caps[stat_name] = {
            'threshold': threshold,
            'penalty_rate': penalty_rate
        }

    def calculate_effective_stats(self, stats):
        """
        Apply all constraints to get effective stat values
        Returns: (effective_stats, wasted_points)
        """
        effective = {}
        wasted_points = {}

        for stat, value in stats.items():
            if stat in self.soft_caps:
                cap = self.soft_caps[stat]
                if value > cap['threshold']:
                    over_threshold = value - cap['threshold']
                    effective_over = over_threshold * cap['penalty_rate']
                    effective[stat] = cap['threshold'] + effective_over
                    wasted_points[stat] = over_threshold * (1 - cap['penalty_rate'])
                else:
                    effective[stat] = value
            else:
                effective[stat] = value

        return effective, wasted_points

    def violates_hard_constraints(self, stats):
        """Check hard constraints (minimums)"""
        violations = []
        for stat, min_val in self.min_constraints.items():
            if stats.get(stat, 0) < min_val:
                violations.append(f"{stat} is {stats.get(stat, 0)}, need at least {min_val}")
        return violations
```

### 3. Upgrade Calculator

Calculates upgraded stats when armor is upgraded. The highest stat on each piece increases by 10%.

```python
class UpgradeCalculator:
    UPGRADE_BOOST = 0.10  # 10% increase

    def get_highest_stat(self, armor_piece):
        """Find the stat with the highest value (excluding metadata)"""
        stats_only = {
            k: v for k, v in armor_piece.items()
            if k not in ['armor_set', 'current_level', 'max_level', 'id', 'armor_type']
        }

        if not stats_only:
            return None, 0

        highest_stat = max(stats_only.items(), key=lambda x: x[1])
        return highest_stat[0], highest_stat[1]

    def calculate_upgraded_stats(self, armor_piece):
        """Calculate what stats would be after upgrade"""
        upgraded = armor_piece.copy()

        highest_stat_name, highest_stat_value = self.get_highest_stat(armor_piece)

        if highest_stat_name:
            upgraded[highest_stat_name] = int(highest_stat_value * (1 + self.UPGRADE_BOOST))

        return upgraded

    def calculate_set_upgraded_stats(self, armor_set):
        """Calculate upgraded stats for all 4 pieces in a set"""
        return [
            self.calculate_upgraded_stats(piece)
            for piece in armor_set
        ]
```

### 4. Preference Adjuster

Lightweight preference learning - no neural networks, instant updates.

```python
class PreferenceAdjuster:
    LEARNING_RATE = 0.1  # How much to adjust per feedback

    def adjust_from_feedback(self, current_weights, feedback):
        """
        feedback format: {
            'thumbs': 'up' | 'down',
            'adjustments': {
                'hero_speed': 'more',  # or 'less'
                'attack': 'less',
            }
        }
        """
        new_weights = current_weights.copy()

        if feedback['thumbs'] == 'up':
            # Increase weights for stats user wants more of
            for stat, direction in feedback['adjustments'].items():
                if direction == 'more':
                    new_weights[stat] = new_weights.get(stat, 0) * (1 + self.LEARNING_RATE)
                elif direction == 'less':
                    new_weights[stat] = new_weights.get(stat, 0) * (1 - self.LEARNING_RATE)
        else:  # thumbs down
            # Reverse the adjustments
            for stat, direction in feedback['adjustments'].items():
                if direction == 'more':
                    new_weights[stat] = new_weights.get(stat, 0) * (1 - self.LEARNING_RATE)
                elif direction == 'less':
                    new_weights[stat] = new_weights.get(stat, 0) * (1 + self.LEARNING_RATE)

        # Normalize weights (optional)
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v/total for k, v in new_weights.items()}

        return new_weights
```

### 5. Future-Proof Scorer

Considers not just current value, but potential value as armor improves.

```python
class FutureProofScorer:
    def calculate_potential_score(self, armor_set, weights, current_inventory=None):
        """
        Score armor considering:
        - Current value (with upgrades)
        - Potential value (if better pieces become available)
        - Flexibility (can be improved incrementally)
        """
        # Current value (with upgrades applied)
        upgraded_pieces = self.upgrade_calculator.calculate_set_upgraded_stats(armor_set)
        current_score = self._score_set(upgraded_pieces, weights)

        # Potential value: how much room for improvement?
        potential_score = self._calculate_improvement_potential(armor_set, current_inventory)

        # Flexibility: how easy is it to swap pieces?
        flexibility_score = self._calculate_flexibility(armor_set, current_inventory)

        # Weighted combination
        total_score = (
            current_score * 0.6 +      # Current value is most important
            potential_score * 0.3 +     # But potential matters
            flexibility_score * 0.1     # Flexibility is nice to have
        )

        return total_score
```

### 6. Incremental Change Evaluator

Evaluates changes to an existing armor set, considering partial replacements.

```python
class IncrementalChangeEvaluator:
    def evaluate_changes(self, current_set, new_inventory, weights):
        """
        current_set: list of 4 currently equipped pieces
        new_inventory: list of new armor pieces to consider
        weights: current preference weights

        Returns: list of recommended changes
        """
        recommendations = []

        # Option 1: Replace single piece
        single_replacements = self._evaluate_single_replacements(
            current_set, new_inventory, weights
        )
        recommendations.extend(single_replacements)

        # Option 2: Replace 2 pieces
        double_replacements = self._evaluate_double_replacements(
            current_set, new_inventory, weights
        )
        recommendations.extend(double_replacements)

        # Option 3: Replace 3 pieces
        triple_replacements = self._evaluate_triple_replacements(
            current_set, new_inventory, weights
        )
        recommendations.extend(triple_replacements)

        # Option 4: Replace all 4 (complete new set)
        complete_replacements = self._evaluate_complete_replacements(
            current_set, new_inventory, weights
        )
        recommendations.extend(complete_replacements)

        # Sort by improvement score
        recommendations.sort(key=lambda x: x['improvement_score'], reverse=True)

        return recommendations
```

### 7. Recommendation Engine

Main engine that combines all components.

```python
class EnhancedRecommendationEngine:
    def get_recommendations(self, inventory, weights, current_set=None,
                           consider_upgrades=True, consider_future=True):
        """
        Main recommendation function

        Args:
            inventory: All available armor pieces
            weights: User preference weights
            current_set: Currently equipped set (for incremental mode)
            consider_upgrades: Whether to factor in upgrade potential
            consider_future: Whether to consider future-proofing
        """
        # Group by set type
        sets_by_type = self._group_by_set_type(inventory)

        # Generate complete sets
        complete_sets = []
        for set_type, pieces in sets_by_type.items():
            if len(pieces) >= 4:  # Need at least 4 pieces for complete set
                complete_sets.extend(self._generate_complete_sets(pieces))

        # Score all sets
        scored_sets = []
        for armor_set in complete_sets:
            # Check hard constraints first
            aggregated = self._aggregate_stats(armor_set)
            violations = self.constraint_manager.violates_hard_constraints(aggregated)
            if violations:
                continue  # Skip sets that violate hard constraints

            # Apply soft caps and get effective stats
            effective_stats, wasted = self.constraint_manager.calculate_effective_stats(aggregated)

            # Calculate score
            if consider_upgrades:
                upgraded_pieces = [
                    self.upgrade_calculator.calculate_upgraded_stats(p)
                    for p in armor_set
                ]
                upgraded_aggregated = self._aggregate_stats(upgraded_pieces)
                effective_upgraded, _ = self.constraint_manager.calculate_effective_stats(upgraded_aggregated)
                score = self._score_stats(effective_upgraded, weights)
            else:
                score = self._score_stats(effective_stats, weights)

            # Apply waste penalty (prefer sets that don't waste stat points)
            waste_penalty = sum(wasted.values()) * 0.1
            score -= waste_penalty

            # Add future-proofing if requested
            if consider_future:
                potential_bonus = self.future_proof_scorer.calculate_potential_score(
                    armor_set, weights, inventory
                )
                score += potential_bonus * 0.2

            scored_sets.append({
                'set': armor_set,
                'score': score,
                'stats': effective_stats,
                'wasted_points': wasted,
                'upgraded_stats': effective_upgraded if consider_upgrades else None
            })

        # Sort by score
        scored_sets.sort(key=lambda x: x['score'], reverse=True)

        # If incremental mode, also evaluate changes
        if current_set:
            changes = self.incremental_evaluator.evaluate_changes(
                current_set, inventory, weights
            )
            return {
                'new_sets': scored_sets[:10],
                'incremental_changes': changes[:10]
            }

        return {'new_sets': scored_sets[:10]}
```

## API Design

### Endpoints

#### GET `/api/recommendations`
Get top armor set recommendations.

**Query Parameters:**
- `limit`: Number of recommendations (default: 10)
- `consider_upgrades`: Whether to factor upgrades (default: true)
- `consider_future`: Whether to consider future-proofing (default: true)

**Request Body (optional):**
```json
{
  "weights": {
    "defense": 0.5,
    "attack": 0.3,
    "hero_speed": 0.2
  },
  "constraints": {
    "min": {"attack": 800},
    "soft_caps": {"hero_speed": {"threshold": 100, "penalty_rate": 0.5}}
  },
  "current_set": [...]  // For incremental mode
}
```

**Response:**
```json
{
  "recommendations": [
    {
      "set_id": "chain_set_001",
      "pieces": [...],
      "current_stats": {...},
      "upgraded_stats": {...},
      "effective_stats": {...},
      "wasted_points": {...},
      "score": 0.85,
      "potential_score": 0.12,
      "flexibility_score": 0.08
    }
  ],
  "incremental_changes": [
    {
      "type": "single_replacement",
      "position": 0,
      "improvement": 0.15,
      "old_piece": {...},
      "new_piece": {...}
    }
  ]
}
```

#### POST `/api/feedback`
Submit user feedback to adjust preferences and constraints.

**Request Body:**
```json
{
  "recommendation_id": "chain_set_001",
  "thumbs": "down",
  "adjustments": {
    "hero_speed": "more",
    "attack": "less"
  },
  "soft_cap_discovery": {
    "hero_speed": 100
  },
  "min_constraint_discovery": {
    "attack": 800
  }
}
```

**Response:**
```json
{
  "updated_weights": {...},
  "updated_constraints": {...},
  "new_recommendations": [...]
}
```

#### GET `/api/preferences`
Get current user preference weights.

**Response:**
```json
{
  "weights": {
    "defense": 0.5,
    "attack": 0.3,
    "hero_speed": 0.2
  },
  "constraints": {
    "min": {"attack": 800},
    "soft_caps": {"hero_speed": {"threshold": 100, "penalty_rate": 0.5}}
  }
}
```

#### PUT `/api/preferences`
Update user preferences manually.

**Request Body:**
```json
{
  "weights": {
    "defense": 0.6,
    "attack": 0.4
  }
}
```

#### POST `/api/constraints`
Add or update constraints.

**Request Body:**
```json
{
  "min": {"attack": 800},
  "soft_caps": {
    "hero_speed": {
      "threshold": 100,
      "penalty_rate": 0.5
    }
  }
}
```

#### GET `/api/stats/ranges`
Get stat ranges for normalization.

**Response:**
```json
{
  "hero_speed": {"min": 0, "max": 100},
  "defense": {"min": 0, "max": 5000},
  ...
}
```

## Frontend Components

### FeedbackPanel Component

Structured feedback UI with buttons (no text input).

```typescript
interface Feedback {
  thumbs: 'up' | 'down';
  adjustments: Record<string, 'more' | 'less'>;
  softCapDiscovery?: Record<string, number>;
  minConstraintDiscovery?: Record<string, number>;
}

// UI Layout:
// - Thumbs Up / Thumbs Down buttons (prominent)
// - For each stat in the recommendation:
//   - Stat name and value
//   - "More" button | "Less" button
// - "Add Soft Cap" button (opens modal: "I have X, but Y is enough")
// - "Add Minimum" button (opens modal: "I need at least X")
// - "Submit Feedback" button
```

### RecommendationCard Component

Displays a recommended armor set with:
- All 4 pieces listed
- Current stats vs upgraded stats
- Wasted points highlighted (over soft caps)
- Potential improvement score
- Flexibility score

### IncrementalChangeView Component

Shows incremental changes when user has existing set:
- "Replace shoulder_pad: +50 score improvement"
- Side-by-side comparison of old vs new piece
- Shows upgraded stats for both
- "Apply Change" button

### UpgradePreview Component

Shows stats with upgrades applied:
- Current stats
- Upgraded stats (with highlight on boosted stat)
- Difference calculation

## Key Workflows

### Workflow A: Initial Recommendation
1. User sets goal: "Maximize Defense + Attack"
2. System shows top recommendations (with upgrades considered)
3. User sees recommendation with Speed=120, but only needs 100
4. User clicks "Set Soft Cap: Speed = 100"
5. System re-ranks, penalizing sets with Speed > 100
6. New recommendations appear

### Workflow B: Incremental Change
1. User has 4 pieces equipped
2. New batch of armor imported
3. System evaluates:
   - Single piece replacements
   - Double piece replacements
   - Complete set replacements
4. Shows: "Replace shoulder_pad: +50 score improvement"
5. Shows upgraded stats for both old and new

### Workflow C: Future-Proofing
1. System shows recommendation
2. Also shows "Potential Improvement: +200 if better mask found"
3. User can see which pieces are "bottlenecks"
4. System prioritizes sets with room to grow

### Workflow D: Reactive Constraint Discovery
1. User sees recommendation with Attack=600
2. User realizes they need at least 800 attack
3. User clicks "Add Minimum: Attack = 800"
4. System immediately filters out sets with Attack < 800
5. New recommendations appear

## Implementation Priority

### Phase 1 (MVP)
- Load armor data from JSON
- Filter to complete sets only
- Basic weighted scoring
- Simple feedback (thumbs up/down)
- Manual weight adjustment
- Hard constraints (minimums)

### Phase 2
- Upgrade calculations
- Soft caps (diminishing returns)
- Stat normalization
- Reactive constraint discovery
- Better ranking algorithm

### Phase 3
- Future-proofing scoring
- Incremental change evaluation
- Flexibility scoring
- Waste point calculations
- Advanced UI components

### Phase 4
- Comparison tools
- What-if analysis
- Visualization
- Export/import preferences
- Performance optimizations

## Technical Notes

### Performance Considerations
- Pre-compute all complete sets on data load
- Cache normalized stats
- Re-ranking is fast (just re-sort by new weights)
- Consider indexing by set type for faster lookups

### Data Loading
- Load from `data/collected.json` (or similar)
- Validate data structure
- Group by set type immediately
- Generate complete sets upfront

### Stat Types
From `extract_gear/index.py`:
- `base`, `fire`, `electric`, `poison`
- `hero_hp`, `hero_dmg`, `hero_rate`, `hero_speed`
- `offense`, `defense`
- `tower_hp`, `tower_dmg`, `tower_rate`, `tower_range`

### Armor Types
From `extract_gear/constants.py` (7 types total):
- `shoulder_pad`, `mask`, `hat`, `greaves`, `shield`, `bracer`, `belt`

Note: A complete armor set requires 4 pieces from the same set, but there are 7 possible armor types. Any combination of 4 different armor types from the same set forms a complete set.

### Set Types
From `extract_gear/constants.py` (8 types total):
- `Chain Armor Set`, `Dark Lord's Set`, `Dragon Slayer Set`
- `Goblin Raider Set`, `Great Hero Set`, `Leather Armor Set`
- `Knight Set`, `Plate Armor Set`

## Future Enhancements

1. **Comparison Mode**: Side-by-side comparison of top 3 recommendations
2. **What-If Analysis**: "If I upgrade this piece, how does ranking change?"
3. **Set Explorer**: Browse all complete sets, filter by constraints
4. **Export/Import Preferences**: Save preference profiles
5. **Visualization**: Charts showing stat distributions, trade-offs
6. **Batch Import**: Import multiple JSON files
7. **History**: Track recommendation history and user choices
8. **Multi-Profile**: Support multiple preference profiles
