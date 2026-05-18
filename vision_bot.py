import re
import time
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

import botconfig
import adb_util
import siliflow_client
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


def try_tap_template(template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0), sleep_after: Optional[float] = None) -> Optional[Dict[str, Any]]:
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


def try_tap_best(template_paths: Sequence[str], threshold: float = 0.8, extra_offset: Tuple[int, int] = (0, 0), sleep_after: Optional[float] = None) -> Optional[Dict[str, Any]]:
    img_bgr = screenshot_bgr()
    matched = match_best_of_templates(img_bgr, template_paths, threshold=threshold)
    if matched is None:
        return None
    tpl = str(matched["template"])
    top_left = matched["top_left"]
    pt = tap_matched_center(tpl, top_left, extra_offset=extra_offset)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S if sleep_after is None else float(sleep_after))
    return {"template": tpl, "top_left": top_left, "confidence": float(matched["confidence"]), "tap": pt}


def tap_screen_center(sleep_after: float = 0.0) -> Tuple[int, int]:
    img_bgr = screenshot_bgr()
    h, w = img_bgr.shape[:2]
    x = int(w / 2)
    y = int(h / 2)
    adb_util.tap(x, y)
    if float(sleep_after) > 0:
        time.sleep(float(sleep_after))
    return x, y

def navigate_to_coord(x: int, y: int) -> Dict[str, Any]:
    step_sleep_s = botconfig.ANDROID_STEP_SLEEP_S
    thr_map_button = botconfig.ANDROID_THR_MAP_BUTTON
    thr_map_x = botconfig.ANDROID_THR_MAP_X
    thr_map_y = botconfig.ANDROID_THR_MAP_Y
    thr_map_go = botconfig.ANDROID_THR_MAP_GO

    tpl_map_x = "assets/android/map/map_x.jpg"
    tpl_map_y = "assets/android/map/map_y.jpg"
    tpl_map_go = "assets/android/map/map_go.jpg"

    tpl_map_button = botconfig.ANDROID_TPL_MAP_BUTTON
    tpl_map_button_2 = botconfig.ANDROID_TPL_MAP_BUTTON_2

    def _match_once(img_bgr: np.ndarray, template_path: str, threshold: float):
        ok, _, locations = match_template(img_bgr, template_path, threshold=threshold, find_all=True)
        if not ok or not locations:
            return None
        return _pick_best_location(locations)

    def _match_best_of_templates(img_bgr: np.ndarray, template_paths, threshold: float):
        best = None
        for tpl in template_paths:
            loc = _match_once(img_bgr, tpl, threshold=threshold)
            if loc is None:
                continue
            (top_left, conf) = loc
            if best is None or conf > best["confidence"]:
                best = {"template": tpl, "top_left": top_left, "confidence": float(conf)}
        return best

    def _tap_matched_center_local(template_path: str, top_left: Tuple[int, int], extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        img_bgr = screenshot_bgr()
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        adb_util.tap(cx, cy)
        return cx, cy

    def _tap_template(template_path: str, threshold: float, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        img_bgr = screenshot_bgr()
        best = _match_once(img_bgr, template_path, threshold=threshold)
        if best is None:
            raise RuntimeError(f"模板匹配失败: {template_path}")
        (top_left, _) = best
        pt = _tap_matched_center_local(template_path, top_left, extra_offset=extra_offset)
        time.sleep(step_sleep_s)
        return pt

    img0 = screenshot_bgr()
    matched_map_btn = _match_best_of_templates(img0, [tpl_map_button, tpl_map_button_2], threshold=thr_map_button)
    if matched_map_btn is None:
        raise RuntimeError("地图按钮模板匹配失败")
    p_map_button = {
        "template": str(matched_map_btn["template"]),
        "top_left": matched_map_btn["top_left"],
        "confidence": float(matched_map_btn["confidence"]),
        "tap": _tap_matched_center_local(str(matched_map_btn["template"]), matched_map_btn["top_left"]),
    }

    time.sleep(step_sleep_s)
    p_x = _tap_template(tpl_map_x, threshold=thr_map_x)

    adb_ime = botconfig.ANDROID_ADB_IME_ID
    sogou_ime = botconfig.ANDROID_SOGOU_IME_ID
    adb_util.ime_set(adb_ime)
    time.sleep(step_sleep_s)
    adb_util.adbkeyboard_input_text(str(int(x)))
    time.sleep(step_sleep_s)

    p_y = _tap_template(tpl_map_y, threshold=thr_map_y)
    time.sleep(step_sleep_s)
    adb_util.adbkeyboard_input_text(str(int(y)))
    time.sleep(step_sleep_s)

    adb_util.ime_set(sogou_ime)
    time.sleep(step_sleep_s)

    p_go = _tap_template(tpl_map_go, threshold=thr_map_go)
    arrival = wait_until_arrived_by_coord()
    p_exit = None
    exit_error = None
    if bool(arrival.get("arrived")):
        try:
            p_exit = _tap_template(botconfig.ANDROID_TPL_MAP_EXIT, threshold=botconfig.ANDROID_MATCH_THRESHOLD)
        except Exception as e:
            exit_error = str(e)

    return {
        "ok": True,
        "target": (int(x), int(y)),
        "tap_map_button": p_map_button,
        "tap_x": p_x,
        "tap_y": p_y,
        "tap_go": p_go,
        "arrival": arrival,
        "tap_map_exit": p_exit,
        "tap_map_exit_error": exit_error,
    }


def _parse_roi(roi_text: str, env_name: str) -> Tuple[int, int, int, int]:
    parts = [x.strip() for x in str(roi_text or "").split(",")]
    if len(parts) != 4:
        raise RuntimeError(f"{env_name} 格式错误，期望 x1,y1,x2,y2")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError(f"{env_name} 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError(f"{env_name} 数值无效，要求 x2>x1,y2>y1")
    return x1, y1, x2, y2


def _crop_png_bytes(img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> bytes:
    x1, y1, x2, y2 = roi
    cropped = img_bgr[y1:y2, x1:x2]
    ok, buf = cv2.imencode(".png", cropped)
    if not ok:
        raise RuntimeError("PNG 编码失败")
    return bytes(buf)


def _extract_coord(text: str) -> Optional[Tuple[int, int]]:
    s = str(text or "").strip()
    if not s:
        return None
    m = re.search(r"(\d{1,3})\s*[,，]\s*(\d{1,3})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    if "(" in s or "（" in s or ")" in s or "）" in s:
        nums = re.findall(r"\d+", s)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
    return None


def detect_coord_by_roi() -> Dict[str, Any]:
    roi_text = botconfig.ANDROID_COORD_ROI
    if not roi_text:
        return {"ok": False, "reason": "missing_android_coord_roi", "coord": None}
    roi = _parse_roi(roi_text, botconfig.KEY_ANDROID_COORD_ROI)
    img_bgr = screenshot_bgr()
    png_bytes = _crop_png_bytes(img_bgr, roi)
    ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
    raw_text = str(ocr_result.get("content", "")).strip()
    coord = _extract_coord(raw_text)
    return {"ok": True, "coord": coord, "raw_text": raw_text, "roi": list(roi), "raw_ocr": ocr_result}


def wait_until_arrived_by_coord() -> Dict[str, Any]:
    max_wait_s = botconfig.ANDROID_ARRIVAL_MAX_WAIT_S
    interval_s = botconfig.ANDROID_ARRIVAL_CHECK_INTERVAL_S
    stable_need = botconfig.ANDROID_ARRIVAL_STABLE_COUNT
    deadline = time.time() + max(1.0, max_wait_s)
    stable = 0
    last = None
    samples = 0

    while time.time() < deadline:
        r = detect_coord_by_roi()
        samples += 1
        coord = r.get("coord")
        if coord is not None:
            if coord == last:
                stable += 1
            else:
                stable = 1
                last = coord
            if stable >= stable_need:
                return {"arrived": True, "coord": coord, "samples": samples}
        time.sleep(max(0.1, interval_s))

    return {"arrived": False, "coord": last, "samples": samples}


def detect_current_map_by_roi() -> Dict[str, Any]:
    if not botconfig.MHXY_MAP_ROI:
        raise RuntimeError(f"缺少 {botconfig.KEY_MHXY_MAP_ROI}，请在 .env 配置，例如 0,0,120,120")
    roi = _parse_roi(botconfig.MHXY_MAP_ROI, botconfig.KEY_MHXY_MAP_ROI)
    img_bgr = screenshot_bgr()
    png_bytes = _crop_png_bytes(img_bgr, roi)
    sys_util.save_debug_image(img_bgr[roi[1]:roi[3], roi[0]:roi[2]], "android_map_roi_cropped")
    ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
    map_name = str(ocr_result.get("content", "")).strip()
    return {"map_name": map_name, "raw_ocr": ocr_result, "roi": list(roi)}
