import time
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

import botconfig
import adb_util
from local_ocr_util import detect_coord, run_local_ocr
import operator_util
import sys_util

screenshot_bgr = operator_util.screenshot_bgr
get_template_wh = operator_util.get_template_wh
match_once = operator_util.match_once
template_exists = operator_util.template_exists
match_best_of_templates = operator_util.match_best_of_templates
match_first_of_templates = operator_util.match_first_of_templates
tap_matched_center = operator_util.tap_matched_center
tap_template = operator_util.tap_template
try_tap_template = operator_util.try_tap_template
try_tap = operator_util.try_tap
try_tap_with_retry = operator_util.try_tap_with_retry
tap_screen_center = operator_util.tap_screen_center


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


def _normalize_ocr_text(text: str) -> str:
    return "".join(str(text or "").split())


def _image_to_bgr(image: Any) -> np.ndarray:
    if hasattr(image, "shape") and hasattr(image, "dtype"):
        return np.asarray(image).copy()
    if isinstance(image, str):
        img = cv2.imread(image)
        if img is None:
            raise RuntimeError(f"读取图片失败: {image}")
        return img
    if isinstance(image, (bytes, bytearray, memoryview)):
        arr = np.frombuffer(bytes(image), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("图片解码失败")
        return img
    raise RuntimeError(f"不支持的图片输入类型: {type(image)!r}")


def _pick_best_text_match(candidates: Sequence[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
    target = _normalize_ocr_text(keyword)
    if not target:
        return None
    matched = []
    for item in candidates:
        text_norm = _normalize_ocr_text(item.get("text", ""))
        if target in text_norm:
            matched.append(item)
    if not matched:
        return None
    matched.sort(
        key=lambda item: (
            _normalize_ocr_text(item.get("text", "")).startswith(target),
            len(_normalize_ocr_text(item.get("text", ""))),
            float(item.get("score", 0.0)),
        ),
        reverse=True,
    )
    return matched[0]


def find_text_by_local_ocr(image: Any, keyword: str) -> Optional[Dict[str, Any]]:
    resp = run_local_ocr(image, use_det=True, use_cls=False, use_rec=True, log_prefix="[vision_bot]")
    result = resp.get("result")
    debug_img = _image_to_bgr(image)

    candidates = []
    for item in result or []:
        if not isinstance(item, Sequence) or len(item) < 3:
            continue
        box = item[0]
        text = str(item[1] or "").strip()
        try:
            score = float(item[2])
        except Exception:
            score = 0.0
        pts = []
        for pt in box:
            if not isinstance(pt, Sequence) or len(pt) < 2:
                continue
            pts.append((int(round(float(pt[0]))), int(round(float(pt[1])))))
        if len(pts) < 4 or not text:
            continue
        cx = int(round(sum(x for x, _ in pts) / len(pts)))
        cy = int(round(sum(y for _, y in pts) / len(pts)))
        candidates.append({"text": text, "score": score, "box": pts, "center": (cx, cy)})

    print(f"[vision_bot] local_text_ocr texts={[item['text'] for item in candidates]}")
    best = _pick_best_text_match(candidates, keyword)
    if best is None:
        print(f"[vision_bot] local_text_ocr no_match keyword={keyword!r}")
        return None
    print(
        f"[vision_bot] local_text_ocr match keyword={keyword!r} text={best['text']!r} "
        f"score={best['score']:.3f} center={best['center']}"
    )
    debug_draw = debug_img.copy()
    box = np.asarray(best["box"], dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(debug_draw, [box], isClosed=True, color=(0, 0, 255), thickness=3)
    cv2.circle(debug_draw, best["center"], radius=6, color=(255, 0, 0), thickness=-1)
    cv2.putText(
        debug_draw,
        best["text"],
        (best["box"][0][0], max(20, best["box"][0][1] - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    sys_util.save_debug_image(debug_draw, "local_text_ocr_best_match")
    return best


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

    img0 = screenshot_bgr()
    matched_map_btn = match_best_of_templates(img0, [tpl_map_button, tpl_map_button_2], threshold=thr_map_button)
    if matched_map_btn is None:
        raise RuntimeError("地图按钮模板匹配失败")
    p_map_button = {
        "template": str(matched_map_btn["template"]),
        "top_left": matched_map_btn["top_left"],
        "confidence": float(matched_map_btn["confidence"]),
        "tap": tap_matched_center(str(matched_map_btn["template"]), matched_map_btn["top_left"]),
    }

    adb_ime = botconfig.ANDROID_ADB_IME_ID
    sogou_ime = botconfig.ANDROID_SOGOU_IME_ID
    adb_util.ime_set(adb_ime)
    time.sleep(step_sleep_s)
    p_x = tap_template(tpl_map_x, threshold=thr_map_x)
    time.sleep(step_sleep_s)
    adb_util.adbkeyboard_input_text(str(int(x)))
    time.sleep(step_sleep_s)

    p_y = tap_template(tpl_map_y, threshold=thr_map_y)
    time.sleep(step_sleep_s)
    adb_util.adbkeyboard_input_text(str(int(y)))
    time.sleep(step_sleep_s)

    adb_util.ime_set(sogou_ime)
    time.sleep(step_sleep_s)

    p_go = tap_template(tpl_map_go, threshold=thr_map_go)
    arrival = wait_until_arrived_by_coord()
    p_exit = None
    exit_error = None
    if bool(arrival.get("arrived")):
        try:
            p_exit = tap_template(botconfig.ANDROID_TPL_MAP_EXIT, threshold=botconfig.ANDROID_MATCH_THRESHOLD)
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


def detect_coord_by_roi() -> Dict[str, Any]:
    roi_text = botconfig.ANDROID_COORD_ROI
    if not roi_text:
        return {"ok": False, "reason": "missing_android_coord_roi", "coord": None}
    roi = _parse_roi(roi_text, botconfig.KEY_ANDROID_COORD_ROI)
    img_bgr = screenshot_bgr()
    png_bytes = _crop_png_bytes(img_bgr, roi)
    detected = detect_coord(png_bytes, save_debug=bool(botconfig.is_debug()))
    return {"ok": bool(detected.get("ok")), "coord": detected.get("coord"), "roi": list(roi)}


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
    ocr_result = run_local_ocr(png_bytes, use_det=True, use_cls=False, use_rec=True, log_prefix="[vision_bot]")
    parts = []
    for item in ocr_result.get("result") or []:
        if not isinstance(item, Sequence) or len(item) < 2:
            continue
        parts.append(str(item[1] or "").strip())
    map_name = "".join(parts).strip()
    print(f"[vision_bot] current_map raw_text={map_name!r}")
    return {"map_name": map_name, "raw_ocr": ocr_result, "roi": list(roi)}
