from autofanpage.image_candidate_selector import (
    OCRUnavailable,
    choose_best_candidate,
    score_candidate_image,
)


def test_choose_best_candidate_returns_lowest_score(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"candidate-a")
    b.write_bytes(b"candidate-b")

    scored = choose_best_candidate(
        [a, b],
        scorer=lambda path: 10 if path == a else 2,
    )

    assert scored == b


def test_score_candidate_image_falls_back_when_ocr_unavailable(monkeypatch, tmp_path):
    path = tmp_path / "sample.png"
    path.write_bytes(b"sample")

    monkeypatch.setattr(
        "autofanpage.image_candidate_selector._ocr_text_score",
        lambda path: (_ for _ in ()).throw(OCRUnavailable("missing")),
    )
    monkeypatch.setattr(
        "autofanpage.image_candidate_selector._fallback_text_score",
        lambda path: 7.5,
    )

    score = score_candidate_image(path)

    assert score == 7.5
