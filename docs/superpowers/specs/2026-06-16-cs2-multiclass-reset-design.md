# CS2 Multiclass Reset Design

## Goal

Reset the project for a fresh CS2 training cycle and reorganize the code around
the new target: CT/T faction and body/head detection.

## Asset Reset

The old training assets are removed from `videos/`, `datasets/`, and `runs/`.
Base model weights stay under `models/base/` so the next training run can start
from a known YOLO checkpoint without re-downloading.

## Dataset Contract

The new default dataset root is `datasets/cs2_multiclass`. The default class
order is fixed:

```text
0 ct_body
1 ct_head
2 t_body
3 t_head
```

Every future raw image should have a matching YOLO label file. Empty label files
are valid and mean the frame has no target. `classes.txt` is ignored by dataset
building and validation. Enemy/teammate status is derived at runtime from the
player's current side.

## Code Organization

The package is split by responsibility:

- `runtime`: frame sources, detector abstraction, detection data, rendering.
- `dataset`: class schema, annotation data model, frame extraction, split
  building, label validation.
- `review`: review-frame naming, saving, and progress state.
- `app`: CLI, GUI, and interactive OpenCV loops.

Legacy top-level modules remain as thin compatibility wrappers where practical.
The console scripts remain stable.

## Behavior Changes

The annotator becomes multiclass. Number keys select the active class:

```text
1 ct_body
2 ct_head
3 t_body
4 t_head
```

The GUI defaults to `datasets/cs2_multiclass`. Video test/review runs show all
classes when the player side is unknown, or filter to the opposite faction when
the player side is set to CT or T. Dataset preparation writes a four-class
`dataset.yaml`.

## Validation

A new dataset validation command checks for missing labels, labels without
images, malformed YOLO lines, invalid class ids, and normalized coordinate
values outside `[0, 1]`. This catches labeling mistakes before training.

## Safety Boundary

The project remains read-only relative to CS2. It does not read game memory,
inject into processes, control input, create an in-game overlay, or bypass
anti-cheat systems.
