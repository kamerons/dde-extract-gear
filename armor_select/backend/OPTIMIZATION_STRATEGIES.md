# Recommendation Engine Optimization Strategies

This document outlines optimization strategies for reducing the computational complexity of the recommendation engine when dealing with large numbers of armor combinations.

## Current Problem

With large datasets, the number of combinations can exceed 4+ billion, making exhaustive evaluation infeasible. The current approach uses `itertools.product()` to generate all combinations, which becomes computationally prohibitive.

## Core Optimization Principles

**Key Insight**: Instead of eliminating pieces we're uncertain about, we should explore combinations in an ordered fashion - prioritizing the most promising pieces first, while keeping the door open to explore others if needed.

## Optimization Strategies

### 1. Constraint-Based Pruning (Pre-filtering)

**Core Idea**: Before generating combinations, check if a set can possibly satisfy all constraints by calculating the maximum possible stats achievable from that set.

**Implementation Approach**:
- For each armor set, calculate the maximum possible value for each stat by taking the best piece for each stat across all armor types
- If the maximum possible stats cannot satisfy all constraints, skip that entire set
- This eliminates entire sets from consideration without generating any combinations

**Benefits**:
- Eliminates entire sets early (no combinations generated)
- Very fast check (O(pieces) per set)
- No false negatives (if max can't satisfy, no combination can)

**Example**:
```python
def can_set_satisfy_constraints(
    pieces_by_armor_type: Dict[str, List[Dict]],
    constraints: Dict[str, int]
) -> bool:
    """Check if a set can possibly satisfy all constraints."""
    if not constraints:
        return True

    # Calculate maximum possible stats by taking best piece for each stat
    max_possible_stats = {stat: 0 for stat in STAT_TYPES}

    for armor_type, pieces in pieces_by_armor_type.items():
        for stat in STAT_TYPES:
            max_for_type = max((p.get(stat, 0) for p in pieces), default=0)
            max_possible_stats[stat] += max_for_type

    # Check if max possible stats can satisfy all constraints
    for stat, min_val in constraints.items():
        if max_possible_stats.get(stat, 0) < min_val:
            return False

    return True
```

**When to Use**: Always - this is a fast pre-filter that eliminates impossible sets.

---

### 3. Incremental Constraint Checking

**Core Idea**: Check constraints as combinations are being built, not after they're complete. If a partial combination already violates constraints or cannot possibly satisfy them even with the best remaining pieces, prune that branch immediately.

**Implementation Approach**:
- As we build combinations (e.g., in beam search), check constraints incrementally
- For partial combinations, calculate:
  - Current stats (from pieces added so far)
  - Maximum possible stats from remaining pieces
  - If `current + max_remaining < constraint_min`, prune this branch
- This prevents building complete combinations that will fail constraints

**Benefits**:
- Prunes branches early in the search tree
- Works naturally with beam search and other incremental approaches
- Reduces wasted computation on invalid combinations

**Example**:
```python
def can_satisfy_constraints_from_here(
    current_stats: Dict[str, int],
    remaining_armor_types: List[str],
    pieces_by_armor_type: Dict[str, List[Dict]],
    constraints: Dict[str, int]
) -> bool:
    """Check if constraints can still be satisfied from current partial state."""
    if not constraints:
        return True

    # Calculate max possible stats from remaining pieces
    max_remaining = {stat: 0 for stat in STAT_TYPES}

    for armor_type in remaining_armor_types:
        pieces = pieces_by_armor_type[armor_type]
        for stat in STAT_TYPES:
            max_for_type = max((p.get(stat, 0) for p in pieces), default=0)
            max_remaining[stat] += max_for_type

    # Check if current + max remaining can satisfy constraints
    for stat, min_val in constraints.items():
        total_possible = current_stats.get(stat, 0) + max_remaining.get(stat, 0)
        if total_possible < min_val:
            return False

    return True
```

**When to Use**: Can be combined with depth-first search or other incremental approaches. Very effective when constraints are strict.

---

### 4. Early Termination with Priority Queue

**Core Idea**: Use a priority queue (min-heap) to maintain the top N candidates seen so far. Stop evaluation early once we've found enough high-quality candidates and can prove that remaining combinations cannot beat them.

**Implementation Approach**:
- Maintain a min-heap of size `limit` (e.g., top 10)
- As combinations are evaluated:
  - If heap is not full, add the combination
  - If heap is full and new score > min score in heap, replace min
- Optionally: Calculate upper bound for remaining combinations
  - If upper bound < min score in heap, we can stop early
- Sort final heap and return top results

**Benefits**:
- Can stop early if we can prove remaining combinations won't be better
- Memory efficient (only stores top N)
- Works well with ordered exploration (evaluate best pieces first)

**Key Insight for Ordered Exploration**:
- Sort pieces by their individual contribution to the weighted score
- Evaluate combinations in order of expected quality
- This maximizes chances of early termination

**Example**:
```python
import heapq

def priority_queue_recommendations(
    pieces_by_armor_type: Dict[str, List[Dict]],
    weights: Dict[str, float],
    constraints: Dict[str, int],
    limit: int = 10,
    max_evaluations: int = 10000
) -> List[Dict]:
    """Use priority queue with early termination."""
    # Min-heap: (-score, pieces) for max-heap behavior
    heap = []
    evaluations = 0

    # Sort pieces by individual score contribution (ordered exploration)
    sorted_pieces_by_type = {}
    for armor_type, pieces in pieces_by_armor_type.items():
        scored = [(calculate_score(get_piece_stats(p), weights), p)
                  for p in pieces]
        scored.sort(reverse=True)
        sorted_pieces_by_type[armor_type] = [p for _, p in scored]

    # Generate combinations in order (best pieces first)
    for combo in product(*[sorted_pieces_by_type[at] for at in sorted_pieces_by_type.keys()]):
        if evaluations >= max_evaluations:
            break

        evaluations += 1
        stats = aggregate_stats(list(combo))

        if violates_hard_constraints(stats):
            continue

        score = calculate_score(stats, weights)

        # Maintain heap of size limit
        if len(heap) < limit:
            heapq.heappush(heap, (score, list(combo)))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, list(combo)))

        # Optional: Early termination if we can prove remaining won't be better
        # (Requires calculating upper bound for remaining combinations)

    # Return top results
    return sorted([(score, pieces) for score, pieces in heap],
                  reverse=True)[:limit]
```

**When to Use**: When you want to limit total evaluations and are okay with potentially missing optimal solutions. Best combined with ordered exploration and depth-first search.

---

### 5. Stat Aggregation Caching

**Core Idea**: Cache the results of expensive computations (stat aggregation, normalization, scoring) to avoid recomputing the same values multiple times.

**Implementation Approach**:
- Use `functools.lru_cache` or a custom cache for:
  - Piece stats extraction (`get_piece_stats`)
  - Stat normalization (`normalize_stat`)
  - Individual piece scoring
- Cache keys should be based on piece IDs or immutable piece data
- Cache size should be tuned based on memory constraints

**Benefits**:
- Reduces redundant computation
- Especially helpful when same pieces appear in multiple combinations
- Low overhead, high impact when pieces are reused

**Example**:
```python
from functools import lru_cache

class RecommendationEngine:
    def __init__(self, inventory: List[Dict]):
        self.inventory = inventory
        # Create piece ID to piece mapping for caching
        self._piece_cache = {p.get('id'): p for p in inventory}

    @lru_cache(maxsize=10000)
    def _get_cached_piece_stats(self, piece_id: str) -> Dict[str, int]:
        """Cache piece stats computation."""
        piece = self._piece_cache.get(piece_id)
        if not piece:
            return {}
        return self.get_piece_stats(piece)

    @lru_cache(maxsize=100000)
    def _get_cached_normalized_stat(self, stat_name: str, value: int) -> float:
        """Cache stat normalization."""
        return self.stat_normalizer.normalize_stat(stat_name, value)
```

**When to Use**: Always - caching has minimal overhead and provides consistent speedups, especially when evaluating many combinations with overlapping pieces.

**Note**: Be careful with cache size - too large can cause memory issues. Monitor memory usage and adjust `maxsize` accordingly.

---

### 6. Parallel Processing

**Core Idea**: Evaluate multiple combinations simultaneously using multiple CPU cores. This doesn't reduce the number of combinations but makes evaluation faster.

**Implementation Approach**:
- Use `multiprocessing.Pool` to distribute combination evaluation across cores
- Each worker evaluates a batch of combinations
- Collect results and merge (sort by score, take top N)
- Consider chunking combinations into batches for better load balancing

**Benefits**:
- Linear speedup with number of cores (up to a point)
- Works well with other optimizations (can parallelize beam search, priority queue, etc.)
- Good for CPU-bound workloads

**Challenges**:
- Overhead from process creation and communication
- Need to serialize/deserialize data (pieces, weights, constraints)
- Memory usage increases with number of workers

**Example Structure**:
```python
from multiprocessing import Pool
from functools import partial

def _evaluate_combination_batch(args):
    """Evaluate a batch of combinations (for parallel processing)."""
    combos, weights, constraints, engine_config = args
    results = []

    for combo in combos:
        stats = aggregate_stats(list(combo))
        if violates_hard_constraints(stats, constraints):
            continue
        score = calculate_score(stats, weights)
        results.append((score, list(combo)))

    return results

def parallel_recommendations(
    pieces_by_armor_type: Dict[str, List[Dict]],
    weights: Dict[str, float],
    constraints: Dict[str, int],
    limit: int = 10,
    num_workers: int = 4,
    batch_size: int = 1000
) -> List[Dict]:
    """Evaluate combinations in parallel."""
    # Generate combinations (potentially limited/sorted)
    all_combos = list(product(*[pieces_by_armor_type[at]
                                for at in pieces_by_armor_type.keys()]))

    # Chunk combinations into batches
    batches = [all_combos[i:i+batch_size]
               for i in range(0, len(all_combos), batch_size)]

    # Evaluate batches in parallel
    with Pool(num_workers) as pool:
        batch_args = [(batch, weights, constraints, None) for batch in batches]
        batch_results = pool.map(_evaluate_combination_batch, batch_args)

    # Merge results and return top limit
    all_results = [r for batch_result in batch_results for r in batch_result]
    all_results.sort(reverse=True, key=lambda x: x[0])
    return all_results[:limit]
```

**When to Use**:
- When you have multiple CPU cores available
- When evaluation is CPU-bound (not I/O bound)
- Best combined with other optimizations (don't parallelize 4 billion combinations, parallelize a reduced set)

**Best Practices**:
- Start with 2-4 workers, measure performance, adjust
- Use larger batch sizes to reduce communication overhead
- Consider using `multiprocessing.Pool` with `imap` for streaming results
- Be mindful of memory usage with large datasets

---

## Depth-First Search with Ordered Exploration

**Core Principle**: Instead of using beam search, evaluate complete sets one at a time using depth-first traversal. Sort pieces by quality first to explore best combinations early.

**Implementation**:
1. **Sort pieces by individual contribution**: For each armor type, sort pieces by their weighted score contribution
2. **Generate combinations in order**: Use sorted pieces in `product()`, so best combinations are generated first
3. **Evaluate depth-first**: Process complete sets one at a time
4. **Maintain priority queue**: Keep top N results in a min-heap as we evaluate
5. **Early termination**: Stop once we've found enough good candidates or timeout is reached

**Benefits**:
- Finds good solutions quickly (evaluates best combinations first)
- Enables early return when timeout is reached
- Memory efficient (only stores top N results, not intermediate states)
- Works naturally with ordered exploration and early termination

**Example**:
```python
import heapq
import time

def depth_first_recommendations(
    pieces_by_armor_type: Dict[str, List[Dict]],
    weights: Dict[str, float],
    constraints: Dict[str, int],
    limit: int = 10,
    timeout_seconds: float = 10.0
) -> List[Dict]:
    """Use depth-first search with ordered exploration."""
    # Sort pieces by quality
    sorted_pieces = ordered_exploration(pieces_by_armor_type, weights)

    # Priority queue (min-heap) for top N results
    heap = []  # Stores (score, pieces, stats) tuples
    start_time = time.time()
    evaluated = 0
    total_planned = calculate_total_combinations(sorted_pieces)

    # Generate combinations in order (best pieces first)
    for combo in product(*[sorted_pieces[at] for at in sorted_pieces.keys()]):
        if time.time() - start_time >= timeout_seconds:
            break

        evaluated += 1
        stats = aggregate_stats(list(combo))

        if violates_hard_constraints(stats, constraints):
            continue

        score = calculate_score(stats, weights)

        # Maintain heap of size limit
        if len(heap) < limit:
            heapq.heappush(heap, (score, list(combo), stats))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, list(combo), stats))

    # Return top results
    return sorted([(score, pieces, stats) for score, pieces, stats in heap],
                  reverse=True)[:limit]
```

---

## Ordered Exploration Strategy

**Core Principle**: Instead of eliminating pieces, sort them by quality and explore best ones first.

**Implementation**:
1. **Sort pieces by individual contribution**: For each armor type, sort pieces by their weighted score contribution
2. **Generate combinations in order**: Use sorted pieces in `product()`, so best combinations are generated first
3. **Early termination**: Stop once we've found enough good candidates
4. **Fallback**: If needed, can expand to lower-ranked pieces

**Benefits**:
- Finds good solutions quickly
- Doesn't eliminate pieces (can still explore if needed)
- Works naturally with early termination
- Respects uncertainty - we explore best options first but keep others available

**Example**:
```python
def ordered_exploration(
    pieces_by_armor_type: Dict[str, List[Dict]],
    weights: Dict[str, float]
) -> Dict[str, List[Dict]]:
    """Sort pieces by quality for ordered exploration."""
    sorted_pieces = {}

    for armor_type, pieces in pieces_by_armor_type.items():
        # Score each piece individually
        scored = []
        for piece in pieces:
            stats = get_piece_stats(piece)
            score = calculate_score(stats, weights)
            scored.append((score, piece))

        # Sort by score (best first)
        scored.sort(reverse=True, key=lambda x: x[0])
        sorted_pieces[armor_type] = [p for _, p in scored]

    return sorted_pieces
```

---

## Recommended Implementation Order

1. **Constraint-Based Pruning** (Strategy 1) - Fast pre-filter, always implement
2. **Ordered Exploration** - Sort pieces by quality, explore best first
3. **Stat Aggregation Caching** (Strategy 5) - Low overhead, always helps
4. **Depth-First Search with Priority Queue** - Main workhorse for large combination spaces
5. **Early Termination** (Strategy 4) - Fine-tune performance with timeout
6. **Incremental Constraint Checking** (Strategy 3) - Optional optimization for future use
7. **Parallel Processing** (Strategy 6) - Final optimization for speed

## Combining Strategies

These strategies work best when combined:
- **Constraint pruning** eliminates impossible sets early
- **Ordered exploration** ensures we see best combinations first
- **Depth-first search** with **priority queue** evaluates complete sets efficiently
- **Caching** speeds up repeated computations
- **Early termination** stops once we have good enough solutions or timeout is reached
- **Parallel processing** speeds up the remaining work

## Performance Targets

- **Current**: 4+ billion combinations (infeasible)
- **Target with optimizations**: <100K combinations evaluated
- **Expected speedup**: 40,000x+ reduction in combinations evaluated
