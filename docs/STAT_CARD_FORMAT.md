# Stat Card Format

This document describes the layout and content of a **stat card**: the region on a gear card that shows armor stats, optional hero stats, optional tower stats, and the level. The format is implemented and used by the image splitters and region extraction logic in this repo.

## References

- **Image splitter (legacy):** `legacy/extract_gear/image_splitter.py` — defines `STAT_DATA` (3 rows x 6 columns with a pass function) and `LEVEL_DATA` (2 rows x 3 columns).
- **Region extraction (shared):** `shared/extract_regions.py` — defines `STAT_*` and `LEVEL_*` constants and computes region boxes for the config UI and splitter.
- **Stat normalization:** `shared/stat_normalizer.py` — defines the canonical stat names and normalization ranges for hero and tower stats.
- **Image split collector:** `legacy/extract_gear/image_split_collector.py` — names crops as defense (row 0), row1 (hero), row2 (tower).

## Overview

A stat card has **at most 3 rows** of stat data, plus a **level** displayed at the bottom-right. Which rows appear depends on the gear: if there are no hero stats, the hero row is absent; if there are no tower stats, the tower row is absent. The card width can grow when the hero row has more than 4 stats (up to 6 in a single row).

## Row 1: Armor Stats (top row)

- **Always present.** This is the first row of the card.
- Contains **at least** base resistance and **one other** resistance (e.g. fire, electric, poison).
- In the legacy splitter, this row is laid out as **4 cells** (columns 0–3 of the stat grid). Columns 4 and 5 are skipped for this row (`col >= 4 and row != 1` in `STAT_DATA.pass_fn`).
- The image split collector labels these crops as `defense_*`.

## Row 2: Hero Data (middle row)

- **Optional.** If the gear has no hero stats, this row does not appear.
- When present, stats are those defined in `shared/stat_normalizer.py` for hero normalization:
  - **HP** (`hero_hp`)
  - **Damage** (`hero_dmg`)
  - **Cast rate** (`hero_rate`)
  - **Speed** (`hero_speed`)
  - **Offense power** (`offense`)
  - **Defense power** (`defense`)
- The stat grid reserves **6 cells** for this row (all columns 0–5). If there are **more than 4** hero stats, the **entire card is wider**, with up to **all 6 stats in a single row**.
- The image split collector labels these crops as `row1_*`.

## Row 3: Tower Stats (bottom row)

- **Optional.** If the gear has no tower stats, this row does not appear. When neither hero nor tower stats exist, the third row is empty and contains nothing.
- When present, the stats are:
  - **HP** (`tower_hp`)
  - **Damage** (`tower_dmg`)
  - **Fire rate** (`tower_rate`)
  - **Range** (`tower_range`)
- In the legacy splitter, this row is laid out as **4 cells** (columns 0–3); columns 4 and 5 are skipped for this row.
- The image split collector labels these crops as `row2_*`.

## Level (bottom-right)

- The **level** is displayed at the **bottom right** of the card.
- Its **position varies** depending on how many of the three stat rows are present and how wide the card is (e.g. 4 vs 6 hero stats).
- In the legacy splitter, the level region is defined by `LEVEL_DATA`: a 2x3 grid with one cell skipped (`row == 0 and col == 2`), yielding **5 possible level positions**. The actual position used depends on card layout (which rows exist and card width).
- Level text is parsed via the **digit detector** (cluster extraction + model) in `shared/card_verification.py` and `shared/level_digit_extract.py`, with OCR fallback when the digit path fails.

## Stat grid summary (legacy splitter)

| Row index | Content   | Grid cells used     | Notes                          |
|-----------|-----------|---------------------|--------------------------------|
| 0         | Armor     | 4 (cols 0–3)        | Base + at least one other res. |
| 1         | Hero      | 6 (cols 0–5)        | Optional; >4 stats = wider card |
| 2         | Tower     | 4 (cols 0–3)        | Optional; can be empty         |

Level: separate 2x3 grid, 5 positions; bottom-right of card, position varies with layout.
