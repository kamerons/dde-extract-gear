#!/usr/bin/env python3
"""
Statistical analysis of armor stats from collected JSON.
Computes per-stat min/max/mean/std (only over armors that have that stat),
compares means within groups, and checks hero_speed cap.
"""

import json
import statistics
import sys
from pathlib import Path

# All known stat keys
RESISTANCE_STATS = ("fire", "electric", "poison")
HERO_TOWER_STATS = (
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
)
ALL_STATS = ("base",) + RESISTANCE_STATS + HERO_TOWER_STATS


def load_armor_data(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def collect_per_stat_values(records: list[dict]) -> dict[str, list[int]]:
    by_stat = {s: [] for s in ALL_STATS}
    for r in records:
        stats = r.get("stats") or {}
        for stat, val in stats.items():
            if stat in by_stat and isinstance(val, (int, float)):
                by_stat[stat].append(int(val))
    return by_stat


def summarize(values: list[int]) -> dict | None:
    if not values:
        return None
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 2),
        "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
    }


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = repo / "data" / "collected" / "armor_run1.json"
    if not path.exists():
        print(f"Missing: {path}", file=sys.stderr)
        sys.exit(1)

    records = load_armor_data(path)
    by_stat = collect_per_stat_values(records)

    print("=== Per-stat summary (armors that have this stat) ===\n")
    for stat in ALL_STATS:
        vals = by_stat[stat]
        s = summarize(vals)
        if s:
            print(f"  {stat:12}  n={s['n']:3}  min={s['min']:4}  max={s['max']:4}  mean={s['mean']:7.2f}  stdev={s['stdev']:6.2f}")
        else:
            print(f"  {stat:12}  (no data)")

    print("\n=== Hero speed (own scale, game cap 100) ===")
    speed_vals = by_stat["hero_speed"]
    if speed_vals:
        s = summarize(speed_vals)
        print(f"  n={s['n']}  min={s['min']}  max={s['max']}  mean={s['mean']:.2f}  stdev={s['stdev']:.2f}")
        cap = 100
        ok = s["max"] <= cap
        print(f"  Cap check: max={s['max']} vs game cap {cap} -> {'OK' if ok else 'EXCEEDED'}")
        if cap > 0:
            pct = 100 * s["mean"] / cap
            print(f"  Mean as % of cap: {pct:.1f}%")
        # Compare raw scale to hero/tower group (same scale?)
        group = [x for x in HERO_TOWER_STATS if x != "hero_speed"]
        ht_summaries = {st: summarize(by_stat[st]) for st in group}
        ht_means = [ht_summaries[st]["mean"] for st in group if ht_summaries.get(st)]
        if ht_means:
            ht_avg = statistics.mean(ht_means)
            ratio = s["mean"] / ht_avg if ht_avg else 0
            print(f"  Speed vs hero/tower (raw): mean {s['mean']:.2f} vs group avg {ht_avg:.2f} -> speed is {ratio:.2f}x (same scale if ~1.0)")
    else:
        print("  hero_speed: no data")

    print("\n=== Resistance group: fire / electric / poison (same scale?) ===")
    res_summaries = {s: summarize(by_stat[s]) for s in RESISTANCE_STATS}
    means = {s: res_summaries[s]["mean"] for s in RESISTANCE_STATS if res_summaries[s]}
    if means:
        avg_mean = statistics.mean(means.values())
        for s in RESISTANCE_STATS:
            m = means.get(s)
            if m is not None:
                diff = m - avg_mean
                print(f"  {s:8}  mean={m:.2f}  (diff from group avg {avg_mean:.2f}: {diff:+.2f})")
        if len(means) >= 2:
            stdevs = [res_summaries[s]["stdev"] for s in RESISTANCE_STATS if res_summaries[s]]
            pooled_std = (sum(x * x for x in stdevs) / len(stdevs)) ** 0.5 if stdevs else 0
            print(f"  Group mean spread vs typical std: max |diff| = {max(abs(means[s] - avg_mean) for s in means):.2f}, avg stdev ~ {pooled_std:.2f}")

    print("\n=== Base vs resistance (e.g. base mean ~ 2x poison mean?) ===")
    base_s = summarize(by_stat["base"])
    if base_s and means:
        base_mean = base_s["mean"]
        for s in RESISTANCE_STATS:
            m = means.get(s)
            if m and m > 0:
                ratio = base_mean / m
                print(f"  base / {s}:  {base_mean:.2f} / {m:.2f} = {ratio:.2f}x")
    else:
        print("  (insufficient data)")

    print("\n=== Hero+Tower group: same scale? (excluding hero_speed) ===")
    group = [s for s in HERO_TOWER_STATS if s != "hero_speed"]
    ht_summaries = {s: summarize(by_stat[s]) for s in group}
    ht_means = {s: ht_summaries[s]["mean"] for s in group if ht_summaries[s]}
    if ht_means:
        avg_mean = statistics.mean(ht_means.values())
        for s in group:
            m = ht_means.get(s)
            if m is not None:
                diff = m - avg_mean
                print(f"  {s:12}  mean={m:6.2f}  (diff from group avg {avg_mean:.2f}: {diff:+.2f})")
        max_diff = max(abs(ht_means[s] - avg_mean) for s in ht_means)
        stdevs = [ht_summaries[s]["stdev"] for s in group if ht_summaries[s]]
        pooled_std = (sum(x * x for x in stdevs) / len(stdevs)) ** 0.5 if stdevs else 0
        print(f"  Max |diff| from group mean: {max_diff:.2f}, avg stdev ~ {pooled_std:.2f} (similar scale if max_diff ~ within 1-2 stdev)")

    print("\n=== Suggested ranges for StatNormalizer (from observed min/max) ===")
    for stat in ALL_STATS:
        s = summarize(by_stat[stat])
        if s:
            if stat == "hero_speed":
                cap = 100
                print(f"  {stat:12}  (0, {cap})  [game cap; observed max={s['max']}]")
            else:
                print(f"  {stat:12}  (0, {s['max']})  [observed min={s['min']}, max={s['max']}]")
    print()
    return None


if __name__ == "__main__":
    main()
