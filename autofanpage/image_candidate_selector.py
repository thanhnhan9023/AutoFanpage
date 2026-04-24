from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable


class OCRUnavailable(RuntimeError):
    pass


def _ocr_text_score(path: Path) -> float:
    if shutil.which("tesseract") is None:
        raise OCRUnavailable("tesseract not installed")
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "6"],
        capture_output=True,
        text=True,
        check=True,
    )
    text = "".join(ch for ch in result.stdout if ch.isalnum())
    return float(len(text))


def _fallback_text_score(path: Path) -> float:
    return float(path.stat().st_size)


def score_candidate_image(path: Path) -> float:
    try:
        return _ocr_text_score(path)
    except OCRUnavailable:
        return _fallback_text_score(path)


def choose_best_candidate(
    candidates: Iterable[Path],
    *,
    scorer: Callable[[Path], float] = score_candidate_image,
) -> Path:
    return min(candidates, key=scorer)
