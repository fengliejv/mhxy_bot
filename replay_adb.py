import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np


class ReplayStep:
    def __init__(self, t: float, action: str, payload: Dict[str, Any]) -> None:
        self.t = float(t)
        self.action = str(action)
        self.payload = dict(payload)


class ReplayAdbClient:
    def __init__(self, screenshot_paths: Sequence[str], loop: bool = True, sleep_s: float = 0.0) -> None:
        self.screenshot_paths = [str(p) for p in screenshot_paths]
        self.loop = bool(loop)
        self.sleep_s = float(sleep_s)
        self._i = 0
        self.history: List[ReplayStep] = []

    def _next_path(self) -> Optional[str]:
        if not self.screenshot_paths:
            return None
        if self._i >= len(self.screenshot_paths):
            if not self.loop:
                return None
            self._i = 0
        p = self.screenshot_paths[self._i]
        self._i += 1
        return p

    def screenshot_png(self) -> bytes:
        path = self._next_path()
        if path is None:
            raise RuntimeError("ReplayAdbClient: 没有可用截图")
        with open(path, "rb") as f:
            data = f.read()
        if self.sleep_s > 0:
            time.sleep(self.sleep_s)
        self.history.append(ReplayStep(time.time(), "screenshot_png", {"path": path}))
        return data

    def screenshot_bgr(self) -> np.ndarray:
        path = self._next_path()
        if path is None:
            raise RuntimeError("ReplayAdbClient: 没有可用截图")
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"ReplayAdbClient: 截图读取失败: {path}")
        if self.sleep_s > 0:
            time.sleep(self.sleep_s)
        self.history.append(ReplayStep(time.time(), "screenshot_bgr", {"path": path}))
        return img

    def tap(self, x: int, y: int) -> None:
        self.history.append(ReplayStep(time.time(), "tap", {"x": int(x), "y": int(y)}))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.history.append(
            ReplayStep(
                time.time(),
                "swipe",
                {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "duration_ms": int(duration_ms)},
            )
        )

    def keyevent(self, keycode: int) -> None:
        self.history.append(ReplayStep(time.time(), "keyevent", {"keycode": int(keycode)}))

    def input_text(self, text: str) -> None:
        self.history.append(ReplayStep(time.time(), "input_text", {"text": str(text)}))

    def ime_set(self, ime_id: str) -> None:
        self.history.append(ReplayStep(time.time(), "ime_set", {"ime_id": str(ime_id)}))

    def adbkeyboard_input_text(self, text: str) -> None:
        self.history.append(ReplayStep(time.time(), "adbkeyboard_input_text", {"text": str(text)}))

    def start_app(self, package: str, activity: str) -> None:
        self.history.append(ReplayStep(time.time(), "start_app", {"package": str(package), "activity": str(activity)}))


def list_images_in_dir(dir_path: str, name_contains: str = "") -> List[str]:
    p = str(dir_path)
    if not os.path.isdir(p):
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = []
    needle = str(name_contains or "").lower().strip()
    for name in sorted(os.listdir(p)):
        ext = os.path.splitext(name.lower())[1]
        if ext in exts:
            if needle and needle not in name.lower():
                continue
            files.append(os.path.join(p, name))
    return files
