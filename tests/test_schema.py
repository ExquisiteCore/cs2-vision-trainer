from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES


def test_default_class_names_use_visible_cs2_factions_and_parts():
    assert DEFAULT_CLASS_NAMES == (
        "ct_body",
        "ct_head",
        "t_body",
        "t_head",
    )
