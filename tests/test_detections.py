from cs2_vision_trainer.detections import Detection, filter_detections


def test_detection_geometry_returns_width_height_center_and_area():
    detection = Detection(label="enemy", confidence=0.8, xyxy=(10, 20, 30, 60))

    assert detection.width == 20
    assert detection.height == 40
    assert detection.center == (20, 40)
    assert detection.area == 800


def test_filter_detections_applies_confidence_and_label_allow_list():
    detections = [
        Detection(label="enemy", confidence=0.91, xyxy=(0, 0, 10, 10)),
        Detection(label="enemy", confidence=0.20, xyxy=(0, 0, 10, 10)),
        Detection(label="teammate", confidence=0.99, xyxy=(0, 0, 10, 10)),
    ]

    filtered = filter_detections(detections, min_confidence=0.5, allowed_labels={"enemy"})

    assert [item.label for item in filtered] == ["enemy"]
    assert filtered[0].confidence == 0.91
