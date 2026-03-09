# Data layout for extract pipeline

Code in `api/`, `task/`, and `scripts/` must follow this layout. All paths are relative to the repo root; the `data/` directory is gitignored and holds runtime artifacts.

## Unlabeled data

Raw or intermediate assets that do not yet have labels:

| Path | Description |
|------|-------------|
| `data/unlabeled/screenshots/001.png`, `002.png`, … | Full-screen captures from the game (e.g. from the screenshot collection script). |
| `data/unlabeled/icons/001.png`, … | Cropped icon images not yet assigned a stat type. |
| `data/unlabeled/numbers/001.png`, … | Cropped digit (or blob) images not yet assigned a digit label. |
| `data/unlabeled/stat_icons/` | Cropped stat icon images (14 per labeled screenshot) produced from labeled screenshots + origin; not yet assigned a stat type. |

## Labeled data

Ground-truth data used for training and evaluation.

### Screenshots (box detector)

- **Images**: `data/labeled/screenshots/<type>/<id>.png`
  - `<type>` is **user-provided** when organizing or importing screenshots: `regular` (standard armor card) or `blueprint` (blueprint card). The neural network does not classify type; you assign it (e.g. by placing images in the corresponding folder).
  - Example: `data/labeled/screenshots/blueprint/031.png`, `data/labeled/screenshots/regular/001.png`.
- **Box coordinates**: For each image, a companion text file with the same base name holds the **top-left** of the box (origin). Format: a single line with two integers, space-separated: `origin_x origin_y`.
  - Example: `data/labeled/screenshots/blueprint/031.txt` contains the coordinates for the box in `031.png` (e.g. `423 293`).

### Augmented screenshots (box detector training)

- **Path**: `data/labeled/augmented/<type>/<id>_<n>.png` and `data/labeled/augmented/<type>/<id>_<n>.txt`
  - `<type>` is `regular` or `blueprint`. Each file is a shifted variant of a source image from `data/labeled/screenshots/<type>/`.
  - `<id>_<n>` is the base name (e.g. `001_1`, `001_2`) for the Nth augmented copy of source `<id>.png`. The `.txt` has the same format as above: one line `origin_x origin_y` for the box top-left in the augmented image.
  - Example: `data/labeled/augmented/blueprint/031_1.png`, `data/labeled/augmented/blueprint/031_1.txt`.

### Numbers (digit / stat-value classifier)

- **Path**: `data/labeled/numbers/<digit>/<id>.png`
  - `<digit>` is the label (e.g. `0`–`9` or a class like `blob`).
  - Example: `data/labeled/numbers/1/001.png`.

### Icons (stat-type classifier)

- **Path**: `data/labeled/icons/<stat_type>/<id>.png`
  - `<stat_type>` is the stat the icon represents (e.g. `defense`, `hero_speed`).
  - Example: `data/labeled/icons/defense/001.png`.

## Test set

For each of the three training targets (box detector, icon classifier, digit classifier), a defined portion of the labeled data is reserved as a **test set**. The exact ratio or split (e.g. 80/20) can be specified in config or in this doc as a default; the same layout applies, with test samples still living under the paths above and the split indicated by config, index files, or naming convention.
