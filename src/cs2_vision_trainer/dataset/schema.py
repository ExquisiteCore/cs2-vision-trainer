from __future__ import annotations

DEFAULT_CLASS_NAMES: tuple[str, ...] = (
    "ct_body",
    "ct_head",
    "t_body",
    "t_head",
)


def normalize_class_names(class_names: tuple[str, ...] | list[str] | None = None) -> tuple[str, ...]:
    names = tuple(class_names or DEFAULT_CLASS_NAMES)
    cleaned = tuple(name.strip() for name in names if name.strip())
    if not cleaned:
        raise ValueError("at least one class name is required")
    return cleaned


def class_name(class_names: tuple[str, ...], class_index: int) -> str:
    if 0 <= class_index < len(class_names):
        return class_names[class_index]
    return str(class_index)
