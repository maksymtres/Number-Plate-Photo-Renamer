from __future__ import annotations

import os
import re
import shutil
from typing import List

import cv2
import numpy as np
import pytesseract
from pytesseract import Output


WHITELIST = "0123456789abcdeABCDE"
DEFAULT_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def configure_tesseract() -> None:
    custom_path = os.getenv("TESSERACT_CMD", "").strip()
    if custom_path:
        pytesseract.pytesseract.tesseract_cmd = custom_path
        return

    detected_path = shutil.which("tesseract")
    if detected_path:
        pytesseract.pytesseract.tesseract_cmd = detected_path
        return

    for path in DEFAULT_WINDOWS_TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return

    raise RuntimeError(
        "Tesseract executable not found. Install Tesseract or set TESSERACT_CMD."
    )


def _prepare_variants(image: np.ndarray) -> List[np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    _, th1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th2 = cv2.bitwise_not(th1)

    return [th1, th2]


def _clean_ocr_text(text: str) -> str:
    text = text.strip()
    text = text.replace("\n", "")
    text = text.replace("\r", "")
    text = text.replace(" ", "")
    return text


def _score_text(text: str) -> int:
    if not text:
        return -100

    score = 0
    if re.fullmatch(r"[0-9A-Za-z]+", text):
        score += 2
    if re.fullmatch(r"\d{1,4}[A-Za-z]?", text):
        score += 5
    if re.fullmatch(r"\d{1,4}[abcdeABCDE]?", text):
        score += 5
    if len(text) > 5:
        score -= 3
    return score


def _extract_text_and_conf(image: np.ndarray, psm: int) -> tuple[str, float | None]:
    config = f"--oem 1 --psm {psm} -c tessedit_char_whitelist={WHITELIST}"

    data = pytesseract.image_to_data(
        image,
        lang="eng",
        config=config,
        output_type=Output.DICT,
    )

    texts = data.get("text", [])
    confs = data.get("conf", [])

    valid_texts = []
    valid_confs = []

    for text, conf in zip(texts, confs):
        cleaned = _clean_ocr_text(str(text))
        if not cleaned:
            continue

        valid_texts.append(cleaned)

        try:
            conf_value = float(conf)
        except (TypeError, ValueError):
            continue

        if conf_value > 0:
            valid_confs.append(conf_value)

    if not valid_texts:
        return "", None

    merged_text = "".join(valid_texts)

    if not valid_confs:
        return merged_text, None

    mean_conf = sum(valid_confs) / len(valid_confs)
    return merged_text, round(mean_conf, 2)


def recognize_text(plate_region: np.ndarray) -> tuple[str, float | None]:
    configure_tesseract()
    variants = _prepare_variants(plate_region)
    candidates: list[tuple[str, float | None]] = []

    for img in variants:
        for psm in (7, 8):
            text, conf = _extract_text_and_conf(img, psm)
            candidates.append((text, conf))

    if not candidates:
        return "", 0.0

    best_text, best_conf = max(
        candidates,
        key=lambda item: (
            _score_text(item[0]),
            item[1] if item[1] is not None else -1.0,
        ),
    )

    return best_text, best_conf