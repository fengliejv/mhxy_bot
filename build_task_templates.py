import os
from typing import List, Tuple

import cv2


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)


def _crop(img, center_xy: Tuple[int, int], size_wh: Tuple[int, int]):
    h, w = img.shape[:2]
    cx, cy = [int(x) for x in center_xy]
    tw, th = [int(x) for x in size_wh]
    x1 = _clamp(cx - tw // 2, 0, w - 1)
    y1 = _clamp(cy - th // 2, 0, h - 1)
    x2 = _clamp(x1 + tw, x1 + 1, w)
    y2 = _clamp(y1 + th, y1 + 1, h)
    return img[y1:y2, x1:x2].copy()


def build() -> List[str]:
    root = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(root, "assets", "android", "task")
    os.makedirs(out_dir, exist_ok=True)

    outputs = []

    cases = [
        (
            os.path.join(root, "debug_capture", "manual_close_before.png"),
            os.path.join(out_dir, "task_hint_close_x.png"),
            (1818, 90),
            (140, 140),
        ),
        (
            os.path.join(root, "debug_capture", "20260511_085529_android_screencap.png"),
            os.path.join(out_dir, "task_button.png"),
            (2222, 280),
            (280, 140),
        ),
        (
            os.path.join(root, "debug_capture", "ignore_before.png"),
            os.path.join(out_dir, "task_hint_ignore_btn.png"),
            (1767, 952),
            (520, 160),
        ),
    ]

    for src, dst, center, size in cases:
        if not os.path.isfile(src):
            continue
        img = cv2.imread(src, cv2.IMREAD_COLOR)
        if img is None:
            continue
        cropped = _crop(img, center, size)
        ok = cv2.imwrite(dst, cropped)
        if ok:
            outputs.append(dst)

    return outputs


if __name__ == "__main__":
    outs = build()
    for p in outs:
        print(p)
