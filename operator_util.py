import time
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

import adb_util
import botconfig
import sys_util
from image_matcher import match_template

_TPL_WH_CACHE: Dict[str, Tuple[int, int]] = {}


def _pick_best_location(locations):
    if not locations:
        return None
    best = locations[0]
    for loc in locations[1:]:
        if loc[1] > best[1]:
            best = loc
    return best


def _template_center_from_top_left(template_path: str, top_left: Tuple[int, int], extra_offset: Tuple[int, int]) -> Tuple[int, int]:
    tpl = cv2.imread(template_path)
    if tpl is None:
        raise RuntimeError(f"模板读取失败: {template_path}")
    h, w = tpl.shape[:2]
    cx = int(top_left[0] + w / 2 + extra_offset[0])
    cy = int(top_left[1] + h / 2 + extra_offset[1])
    return cx, cy


def screenshot_bgr() -> np.ndarray:
    return adb_util.screenshot_bgr()


def get_template_wh(template_path: str) -> Tuple[int, int]:
    cached = _TPL_WH_CACHE.get(template_path)
    if cached is not None:
        return cached
    tpl = cv2.imread(template_path)
    if tpl is None:
        raise RuntimeError(f"模板读取失败: {template_path}")
    h, w = tpl.shape[:2]
    _TPL_WH_CACHE[template_path] = (w, h)
    return w, h


def match_once(img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None):
    thr = botconfig.ANDROID_MATCH_THRESHOLD if threshold is None else threshold
    ok, _, locations = match_template(img_bgr, template_path, threshold=thr, find_all=True)
    if not ok or not locations:
        return None
    return _pick_best_location(locations)


def template_exists(template_path: str, threshold: Optional[float] = None, img_bgr: Optional[np.ndarray] = None) -> bool:
    img = screenshot_bgr() if img_bgr is None else img_bgr
    return match_once(img, template_path, threshold=threshold) is not None


def match_best_of_templates(img_bgr: np.ndarray, template_paths: Sequence[str], threshold: float):
    best = None
    for tpl in template_paths:
        ok, _, locations = match_template(img_bgr, tpl, threshold=threshold, find_all=True)
        if not ok or not locations:
            continue
        loc = _pick_best_location(locations)
        if loc is None:
            continue
        (top_left, conf) = loc
        if best is None or conf > best["confidence"]:
            best = {"template": tpl, "top_left": top_left, "confidence": conf}
    return best


def match_first_of_templates(img_bgr: np.ndarray, template_paths: Sequence[str], threshold: float):
    for tpl in template_paths:
        ok, _, locations = match_template(img_bgr, tpl, threshold=threshold, find_all=True)
        if not ok or not locations:
            continue
        loc = _pick_best_location(locations)
        if loc is None:
            continue
        (top_left, conf) = loc
        return {"template": tpl, "top_left": top_left, "confidence": conf}
    return None


def tap_matched_center(template_path: str, top_left: Tuple[int, int], extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
    img_bgr = screenshot_bgr()
    cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
    adb_util.tap(cx, cy)
    try:
        dbg = img_bgr.copy()
        cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
        sys_util.save_debug_image(dbg, f"android_tap_{template_path}_{cx}_{cy}")
    except Exception:
        pass
    return cx, cy


def tap_template(template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
    img_bgr = screenshot_bgr()
    best = match_once(img_bgr, template_path, threshold=threshold)
    if best is None:
        raise RuntimeError(f"模板匹配失败: {template_path}")
    (top_left, _) = best
    pt = tap_matched_center(template_path, top_left, extra_offset=extra_offset)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    return pt


def try_tap_template(
    template_path: str,
    threshold: Optional[float] = None,
    extra_offset: Tuple[int, int] = (0, 0),
    sleep_after: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    img_bgr = screenshot_bgr()
    best = match_once(img_bgr, template_path, threshold=threshold)
    if best is None:
        return None
    (top_left, conf) = best
    pt = tap_matched_center(template_path, top_left, extra_offset=extra_offset)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S if sleep_after is None else float(sleep_after))
    return {"template": template_path, "top_left": top_left, "confidence": float(conf), "tap": pt}


def try_tap(template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Optional[Tuple[int, int]]:
    r = try_tap_template(template_path, threshold=threshold, extra_offset=extra_offset)
    if r is None:
        return None
    return tuple(r.get("tap") or ())


def try_tap_with_retry(
    template_path: str,
    threshold: Optional[float] = None,
    retry: Optional[int] = None,
    retry_sleep_s: Optional[float] = None,
    extra_offset: Tuple[int, int] = (0, 0),
) -> Optional[Tuple[int, int]]:
    max_retry = max(1, botconfig.ANDROID_TRANSFER_RETRY if retry is None else int(retry))
    sleep_s = botconfig.ANDROID_TRANSFER_RETRY_SLEEP_S if retry_sleep_s is None else float(retry_sleep_s)
    tapped = None
    for _ in range(max_retry):
        tapped = try_tap(template_path, threshold=threshold, extra_offset=extra_offset)
        if tapped is not None:
            return tapped
        time.sleep(max(0.1, sleep_s))
    return None


def tap_screen_center(sleep_after: float = 0.0) -> Tuple[int, int]:
    img_bgr = screenshot_bgr()
    h, w = img_bgr.shape[:2]
    x = int(w / 2)
    y = int(h / 2)
    adb_util.tap(x, y)
    if float(sleep_after) > 0:
        time.sleep(float(sleep_after))
    return x, y
