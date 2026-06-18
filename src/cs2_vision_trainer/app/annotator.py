from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from cs2_vision_trainer.annotation import (
    AnnotationBox,
    AnnotatorState,
    collect_image_paths,
    draw_annotation_overlay,
    filter_images_missing_labels,
    load_current_boxes,
    normalize_box,
    point_in_box,
    save_current_boxes,
)
from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES


def annotate_images(args: argparse.Namespace) -> int:
    image_paths = collect_image_paths(Path(args.images), pattern=args.pattern)
    if args.missing_only:
        image_paths = filter_images_missing_labels(image_paths, Path(args.labels))
    if not image_paths:
        print(f"no images found: {args.images} pattern={args.pattern}")
        return 1

    state = AnnotatorState(
        image_paths=image_paths,
        labels_dir=Path(args.labels),
        class_index=args.class_index,
        class_names=tuple(args.class_names or DEFAULT_CLASS_NAMES),
    )
    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(args.window, _handle_annotator_mouse, state)
    try:
        while True:
            image = cv2.imread(str(state.current_image_path))
            if image is None:
                print(f"failed to read image: {state.current_image_path}")
                return 1
            image_height, image_width = image.shape[:2]
            if state.boxes is None:
                load_current_boxes(state, image_width=image_width, image_height=image_height)
            output = draw_annotation_overlay(
                image,
                state=state,
                image_width=image_width,
                image_height=image_height,
            )
            cv2.imshow(args.window, output)
            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27):
                save_current_boxes(state, image_width=image_width, image_height=image_height)
                print(f"saved {state.current_label_path}")
                break
            if key in (ord("s"), ord("S")):
                save_current_boxes(state, image_width=image_width, image_height=image_height)
                print(f"saved {state.current_label_path}")
                continue
            if key in (ord("d"), ord("D"), ord(" "), 83):
                save_current_boxes(state, image_width=image_width, image_height=image_height)
                print(f"saved {state.current_label_path}")
                _move_annotator(state, 1)
                continue
            if key in (ord("a"), ord("A"), 81):
                save_current_boxes(state, image_width=image_width, image_height=image_height)
                print(f"saved {state.current_label_path}")
                _move_annotator(state, -1)
                continue
            if key in (ord("x"), ord("X")):
                state.boxes = []
                state.dirty = True
                continue
            if _switch_class_from_key(state, key):
                continue
    finally:
        cv2.destroyWindow(args.window)
    return 0


def _switch_class_from_key(state: AnnotatorState, key: int) -> bool:
    if ord("1") <= key <= ord("9"):
        class_index = key - ord("1")
        if class_index < len(state.class_names):
            state.class_index = class_index
            return True
    return False


def _move_annotator(state: AnnotatorState, delta: int) -> None:
    state.current_index = min(max(state.current_index + delta, 0), len(state.image_paths) - 1)
    state.boxes = None
    state.drawing_start = None
    state.drawing_current = None
    state.dirty = False


def _handle_annotator_mouse(event: int, x: int, y: int, _flags: int, state: AnnotatorState) -> None:
    if state.boxes is None:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        state.drawing_start = (x, y)
        state.drawing_current = (x, y)
        return
    if event == cv2.EVENT_MOUSEMOVE and state.drawing_start:
        state.drawing_current = (x, y)
        return
    if event == cv2.EVENT_LBUTTONUP and state.drawing_start:
        image = cv2.imread(str(state.current_image_path))
        if image is None:
            state.drawing_start = None
            state.drawing_current = None
            return
        image_height, image_width = image.shape[:2]
        x1, y1 = state.drawing_start
        box = normalize_box((x1, y1, x, y), image_width=image_width, image_height=image_height)
        state.drawing_start = None
        state.drawing_current = None
        if box[2] - box[0] >= 3 and box[3] - box[1] >= 3:
            state.boxes.append(AnnotationBox(class_index=state.class_index, xyxy=box))
            state.dirty = True
        return
    if event == cv2.EVENT_RBUTTONDOWN:
        for index in range(len(state.boxes) - 1, -1, -1):
            if point_in_box((x, y), state.boxes[index].xyxy):
                del state.boxes[index]
                state.dirty = True
                break
