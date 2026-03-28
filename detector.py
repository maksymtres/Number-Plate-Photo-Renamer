from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def _resize_if_needed(image: np.ndarray, max_side: int = 1600) -> np.ndarray:
    h, w = image.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return image

    scale = max_side / side
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _preprocess_for_detection(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Для наших табличек ожидаем светлую карточку на более тёмном фоне.
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel, iterations=1)

    return morphed


def _score_candidate(x: int, y: int, w: int, h: int, image_area: int) -> float:
    area = w * h
    area_ratio = area / image_area
    aspect_ratio = w / max(h, 1)

    if area_ratio < 0.01 or area_ratio > 0.6:
        return -1.0
    if aspect_ratio < 1.2 or aspect_ratio > 5.5:
        return -1.0

    score = area_ratio * 10.0
    if 1.8 <= aspect_ratio <= 3.5:
        score += 1.0

    return score


def detect_plate(image_path: Path, debug_dir: Optional[Path] = None) -> np.ndarray | None:
    image = cv2.imread(str(image_path))
    if image is None:
        return None

    image = _resize_if_needed(image)
    processed = _preprocess_for_detection(image)

    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h_img, w_img = image.shape[:2]
    image_area = h_img * w_img

    best_box = None
    best_score = -1.0

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        score = _score_candidate(x, y, w, h, image_area)
        if score > best_score:
            best_score = score
            best_box = (x, y, w, h)

    if best_box is None or best_score < 0:
        return None

    x, y, w, h = best_box

    pad_x = int(w * 0.06)
    pad_y = int(h * 0.08)

    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w_img, x + w + pad_x)
    y2 = min(h_img, y + h + pad_y)

    crop = image[y1:y2, x1:x2].copy()

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_image = image.copy()
        cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imwrite(str(debug_dir / f"{image_path.stem}_detected_box.jpg"), debug_image)
        cv2.imwrite(str(debug_dir / f"{image_path.stem}_processed.jpg"), processed)
        cv2.imwrite(str(debug_dir / f"{image_path.stem}_crop.jpg"), crop)

    return crop
