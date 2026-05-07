import os
from typing import Dict, Tuple, Optional, List

import cv2
import numpy as np

import sys_util


_TEMPLATES: Optional[Dict[str, np.ndarray]] = None


def _assets_digital_dir() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "assets", "digital")


def _binarize_for_digits(img_bgr: np.ndarray) -> np.ndarray:
    if img_bgr is None:
        raise ValueError("img 不能为空")
    if len(img_bgr.shape) == 2:
        gray = img_bgr
    else:
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        lower = np.array([10, 80, 80], dtype=np.uint8)
        upper = np.array([45, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        gray = mask

    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)

    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=1)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
    bw = cv2.resize(bw, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    return bw


def _load_templates() -> Dict[str, np.ndarray]:
    global _TEMPLATES
    if _TEMPLATES is not None:
        return _TEMPLATES

    digital_dir = _assets_digital_dir()
    if not os.path.isdir(digital_dir):
        raise RuntimeError("缺少模板目录: {}".format(digital_dir))

    templates: Dict[str, np.ndarray] = {}
    for name in os.listdir(digital_dir):
        if not name.lower().endswith(".png"):
            continue
        stem = os.path.splitext(name)[0].strip().lower()
        if stem == "dot":
            ch = ","
        elif stem.isdigit() and len(stem) == 1:
            ch = stem
        else:
            continue

        p = os.path.join(digital_dir, name)
        img = cv2.imread(p, cv2.IMREAD_COLOR)
        if img is None:
            continue
        bw = _binarize_for_digits(img)
        templates[ch] = bw

    if not templates:
        raise RuntimeError("未加载到任何数字模板，请检查目录: {}".format(digital_dir))

    _TEMPLATES = templates
    return templates


def _segment_char_boxes(bw: np.ndarray) -> List[Tuple[int, int, int, int]]:
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: List[Tuple[int, int, int, int]] = []
    h, w = bw.shape[:2]
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw * ch < 30:
            continue
        if ch < max(8, int(h * 0.25)):
            continue
        if cw < 2:
            continue
        boxes.append((x, y, x + cw, y + ch))

    boxes.sort(key=lambda b: b[0])

    merged: List[Tuple[int, int, int, int]] = []
    for b in boxes:
        if not merged:
            merged.append(b)
            continue
        px1, py1, px2, py2 = merged[-1]
        x1, y1, x2, y2 = b
        if x1 <= px2 + 2:
            merged[-1] = (px1, min(py1, y1), max(px2, x2), max(py2, y2))
        else:
            merged.append(b)
    return merged


def _match_one_char(char_img_bw: np.ndarray, templates: Dict[str, np.ndarray]) -> Tuple[str, float]:
    best_ch = ""
    best_score = -1.0

    for ch, tpl in templates.items():
        h, w = tpl.shape[:2]
        resized = cv2.resize(char_img_bw, (w, h), interpolation=cv2.INTER_NEAREST)
        score = float(cv2.matchTemplate(resized, tpl, cv2.TM_CCOEFF_NORMED)[0][0])
        if score > best_score:
            best_score = score
            best_ch = ch

    return best_ch, best_score


def ocr_image(img) -> str:
    if img is None:
        raise ValueError("img 不能为空")

    templates = _load_templates()
    bw = _binarize_for_digits(img)
    sys_util.save_debug_image(bw, "digit_bw")

    boxes = _segment_char_boxes(bw)
    if not boxes:
        return ""

    out = []
    for (x1, y1, x2, y2) in boxes:
        pad = 2
        x1p = 0 if x1 - pad < 0 else x1 - pad
        y1p = 0 if y1 - pad < 0 else y1 - pad
        x2p = min(bw.shape[1], x2 + pad)
        y2p = min(bw.shape[0], y2 + pad)
        char_bw = bw[y1p:y2p, x1p:x2p]
        ch, score = _match_one_char(char_bw, templates)
        if not ch:
            continue
        if score < 0.25:
            continue
        out.append(ch)

    return "".join(out)


def ocr_region(img, region_box) -> str:
    x1, y1, x2, y2 = region_box
    roi = img[y1:y2, x1:x2]
    sys_util.save_debug_image(roi, "digit_roi")
    return ocr_image(roi)

def main():
    # 这里是脚本直接运行时的示例入口
    img = cv2.imread("assets/digital/test.PNG")
    result = ocr_image(img)
    print(result)

if __name__ == "__main__":
    # 直接运行该文件时执行 main()
    main()

