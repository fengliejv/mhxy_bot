import os
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

import sys_util
from adb_util import AdbClient
from image_matcher import match_template


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


class AndroidVisionBot:
    def __init__(self, adb: Optional[AdbClient] = None) -> None:
        self.adb = adb or AdbClient()
        self.match_threshold = float(os.getenv("ANDROID_MATCH_THRESHOLD", "0.8").strip() or "0.8")
        self.step_sleep_s = float(os.getenv("ANDROID_STEP_SLEEP_S", "0.4").strip() or "0.4")
        self._tpl_wh_cache: Dict[str, Tuple[int, int]] = {}

    def screenshot_bgr(self) -> np.ndarray:
        return self.adb.screenshot_bgr()

    def _get_template_wh(self, template_path: str) -> Tuple[int, int]:
        cached = self._tpl_wh_cache.get(template_path)
        if cached is not None:
            return cached
        tpl = cv2.imread(template_path)
        if tpl is None:
            raise RuntimeError(f"模板读取失败: {template_path}")
        h, w = tpl.shape[:2]
        self._tpl_wh_cache[template_path] = (w, h)
        return w, h

    def _match_once(self, img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None):
        thr = self.match_threshold if threshold is None else threshold
        ok, _, locations = match_template(img_bgr, template_path, threshold=thr, find_all=True)
        if not ok or not locations:
            return None
        return _pick_best_location(locations)

    def _match_best_of_templates(self, img_bgr: np.ndarray, template_paths, threshold: float):
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

    def _match_first_of_templates(self, img_bgr: np.ndarray, template_paths, threshold: float):
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

    def match_best(self, template_paths, threshold: float = 0.8) -> Optional[Dict]:
        img_bgr = self.screenshot_bgr()
        return self._match_best_of_templates(img_bgr, template_paths, threshold=threshold)

    def _tap_template(self, img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        best = self._match_once(img_bgr, template_path, threshold=threshold)
        if best is None:
            raise RuntimeError(f"模板匹配失败: {template_path}")
        (top_left, _) = best
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        self.adb.tap(cx, cy)
        return cx, cy

    def _tap_matched_center(self, img_bgr: np.ndarray, template_path: str, top_left: Tuple[int, int], extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        self.adb.tap(cx, cy)
        return cx, cy

    def _tap(self, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        pt = self._tap_template(img_bgr, template_path, threshold=threshold, extra_offset=extra_offset)
        time.sleep(self.step_sleep_s)
        return pt

    def _try_tap_template(self, img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0), sleep_after: Optional[float] = None) -> Optional[Dict]:
        best = self._match_once(img_bgr, template_path, threshold=threshold)
        if best is None:
            return None
        (top_left, conf) = best
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        self.adb.tap(cx, cy)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        time.sleep(self.step_sleep_s if sleep_after is None else float(sleep_after))
        return {"template": template_path, "top_left": top_left, "confidence": float(conf), "tap": (cx, cy)}

    def _try_tap(self, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Optional[Tuple[int, int]]:
        img_bgr = self.screenshot_bgr()
        best = self._match_once(img_bgr, template_path, threshold=threshold)
        if best is None:
            return None
        (top_left, _) = best
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        self.adb.tap(cx, cy)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        time.sleep(self.step_sleep_s)
        return cx, cy

    def try_tap_best(self, template_paths, threshold: float = 0.8, extra_offset: Tuple[int, int] = (0, 0), sleep_after: Optional[float] = None) -> Optional[Dict]:
        img_bgr = self.screenshot_bgr()
        matched = self._match_best_of_templates(img_bgr, template_paths, threshold=threshold)
        if matched is None:
            return None
        tpl = str(matched["template"])
        top_left = matched["top_left"]
        pt = self._tap_matched_center(img_bgr, tpl, top_left, extra_offset=extra_offset)
        time.sleep(self.step_sleep_s if sleep_after is None else float(sleep_after))
        return {"template": tpl, "top_left": top_left, "confidence": float(matched["confidence"]), "tap": pt}


def navigate_to_coord(bot: AndroidVisionBot, x: int, y: int) -> Dict[str, Any]:
    thr_map_button = float(os.getenv("ANDROID_THR_MAP_BUTTON", "0.6") or "0.6")
    thr_map_x = float(os.getenv("ANDROID_THR_MAP_X", str(bot.match_threshold)) or bot.match_threshold)
    thr_map_y = float(os.getenv("ANDROID_THR_MAP_Y", str(bot.match_threshold)) or bot.match_threshold)
    thr_map_go = float(os.getenv("ANDROID_THR_MAP_GO", str(bot.match_threshold)) or bot.match_threshold)

    tpl_map_x = "assets/android/map/map_x.jpg"
    tpl_map_y = "assets/android/map/map_y.jpg"
    tpl_map_go = "assets/android/map/map_go.jpg"

    tpl_map_button = os.getenv("ANDROID_TPL_MAP_BUTTON", "assets/android/map/map_button.jpg").strip() or "assets/android/map/map_button.jpg"
    tpl_map_button_2 = os.getenv("ANDROID_TPL_MAP_BUTTON_2", "assets/android/map/map_button2.png").strip() or "assets/android/map/map_button2.png"
    p_map_button = bot.try_tap_best([tpl_map_button, tpl_map_button_2], threshold=thr_map_button)
    if p_map_button is None:
        raise RuntimeError("地图按钮模板匹配失败")

    time.sleep(bot.step_sleep_s)
    p_x = bot._tap(tpl_map_x, threshold=thr_map_x)

    adb_ime = os.getenv("ANDROID_ADB_IME_ID", "com.android.adbkeyboard/.AdbIME").strip() or "com.android.adbkeyboard/.AdbIME"
    sogou_ime = os.getenv("ANDROID_SOGOU_IME_ID", "com.sohu.inputmethod.sogou.xiaomi/.SogouIME").strip() or "com.sohu.inputmethod.sogou.xiaomi/.SogouIME"
    bot.adb.ime_set(adb_ime)
    time.sleep(bot.step_sleep_s)
    bot.adb.adbkeyboard_input_text(str(int(x)))
    time.sleep(bot.step_sleep_s)

    p_y = bot._tap(tpl_map_y, threshold=thr_map_y)
    time.sleep(bot.step_sleep_s)
    bot.adb.adbkeyboard_input_text(str(int(y)))
    time.sleep(bot.step_sleep_s)

    bot.adb.ime_set(sogou_ime)
    time.sleep(bot.step_sleep_s)

    p_go = bot._tap(tpl_map_go, threshold=thr_map_go)
    arrival = None
    waiter = getattr(bot, "wait_until_arrived_by_coord", None)
    if callable(waiter):
        arrival = waiter()

    return {
        "ok": True,
        "target": (int(x), int(y)),
        "tap_map_button": p_map_button,
        "tap_x": p_x,
        "tap_y": p_y,
        "tap_go": p_go,
        "arrival": arrival,
    }
