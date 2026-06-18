from cs2_vision_trainer.detector import select_class_indices


def test_select_class_indices_returns_none_when_no_filter_is_configured():
    names = {0: "ct_body", 1: "ct_head"}

    assert select_class_indices(names, allowed_labels=None) is None
    assert select_class_indices(names, allowed_labels=set()) is None


def test_select_class_indices_matches_exact_label_names():
    names = {0: "ct_body", 1: "ct_head", 2: "t_body"}

    selected = select_class_indices(names, allowed_labels={"ct_body", "ct_head"})

    assert selected == {0, 1}
