import time
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

import botconfig
import adb_util
from local_ocr_util import detect_coord, flatten_ocr_text, run_local_ocr
import operator_util
from roi_util import parse_roi
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


def _mask_to_ocr_bgr(mask: np.ndarray) -> np.ndarray:
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)


def _build_text_ocr_variant_map(img_bgr: np.ndarray) -> Dict[str, np.ndarray]:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    gray_eq = cv2.equalizeHist(gray)
    _, gray_bin = cv2.threshold(gray_eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    white_mask = cv2.inRange(hsv, (0, 0, 170), (180, 85, 255))
    yellow_mask = cv2.inRange(hsv, (12, 80, 130), (42, 255, 255))
    blue_purple_mask = cv2.inRange(hsv, (100, 60, 90), (165, 255, 255))

    return {
        "original": img_bgr,
        "gray_bin": _mask_to_ocr_bgr(gray_bin),
        "yellow_text": _mask_to_ocr_bgr(cv2.bitwise_or(yellow_mask, white_mask)),
        "blue_purple_text": _mask_to_ocr_bgr(cv2.bitwise_or(blue_purple_mask, white_mask)),
    }


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


def _collect_text_ocr_candidates(result: Any) -> Sequence[Dict[str, Any]]:
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
    return candidates


def _collect_text_ocr_candidates_from_variants(
    image: Any,
    log_prefix: str,
    variant_names: Optional[Sequence[str]] = None,
) -> Sequence[Dict[str, Any]]:
    img_bgr = _image_to_bgr(image)
    variant_map = _build_text_ocr_variant_map(img_bgr)
    selected_variant_names = list(variant_names or ("original", "gray_bin"))
    merged = []
    seen = set()
    for variant_name in selected_variant_names:
        variant_image = variant_map.get(str(variant_name))
        if variant_image is None:
            continue
        if bool(botconfig.is_debug()) and variant_name != "original":
            sys_util.save_debug_image(variant_image, f"text_ocr_variant_{variant_name}")
        resp = run_local_ocr(variant_image, use_det=True, use_cls=False, use_rec=True, log_prefix=f"{log_prefix}[{variant_name}]")
        variant_candidates = _collect_text_ocr_candidates(resp.get("result"))
        texts = [item["text"] for item in variant_candidates]
        print(f"{log_prefix} local_text_ocr variant={variant_name} texts={texts}")
        for item in variant_candidates:
            key = (
                _normalize_ocr_text(item.get("text", "")),
                int(item["center"][0]),
                int(item["center"][1]),
            )
            existed = seen.__contains__(key)
            if not existed:
                seen.add(key)
            merged.append(
                {
                    **item,
                    "variant": variant_name,
                    "variant_duplicate": existed,
                }
            )
    return merged


def match_any_text_by_local_ocr(
    image: Any,
    keywords: Sequence[str],
    log_prefix: str = "[vision_bot]",
    variant_names_by_keyword: Optional[Dict[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    variant_cache: Dict[str, Sequence[Dict[str, Any]]] = {}
    all_texts = []
    for keyword in keywords:
        variant_names = tuple((variant_names_by_keyword or {}).get(keyword) or ("original", "gray_bin"))
        candidates = []
        for variant_name in variant_names:
            if variant_name not in variant_cache:
                variant_cache[variant_name] = _collect_text_ocr_candidates_from_variants(
                    image,
                    log_prefix=log_prefix,
                    variant_names=(variant_name,),
                )
            candidates.extend(variant_cache[variant_name])
        texts = [item["text"] for item in candidates]
        all_texts.extend(texts)
        print(f"{log_prefix} local_text_ocr keyword={keyword!r} variants={list(variant_names)!r} texts={texts}")
        best = _pick_best_text_match(candidates, keyword)
        if best is None:
            continue
        print(
            f"{log_prefix} local_text_ocr match keyword={keyword!r} text={best['text']!r} "
            f"score={best['score']:.3f} center={best['center']} variant={best.get('variant')}"
        )
        return {"ok": True, "keyword": keyword, "best": best, "texts": all_texts}

    print(f"{log_prefix} local_text_ocr no_match keywords={list(keywords)!r}")
    return {"ok": False, "keywords": list(keywords), "texts": all_texts}


def tap_any_text_by_local_ocr(
    image: Any,
    keywords: Sequence[str],
    extra_offset: Tuple[int, int] = (0, 0),
    log_prefix: str = "[vision_bot]",
    variant_names_by_keyword: Optional[Dict[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    matched = match_any_text_by_local_ocr(
        image,
        keywords=keywords,
        log_prefix=log_prefix,
        variant_names_by_keyword=variant_names_by_keyword,
    )
    if not bool(matched.get("ok")):
        return matched

    best = matched["best"]
    center = best["center"]
    tap_pt = (int(center[0]) + int(extra_offset[0]), max(0, int(center[1]) + int(extra_offset[1])))
    adb_util.tap(tap_pt[0], tap_pt[1])
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    return {
        "ok": True,
        "keyword": matched.get("keyword"),
        "text": best.get("text"),
        "score": float(best.get("score", 0.0)),
        "center": center,
        "tap": tap_pt,
    }


def find_text_by_local_ocr(image: Any, keyword: str) -> Optional[Dict[str, Any]]:
    debug_img = _image_to_bgr(image)
    variant_names = ("original", "gray_bin")
    candidates = _collect_text_ocr_candidates_from_variants(image, log_prefix="[vision_bot]", variant_names=variant_names)

    print(f"[vision_bot] local_text_ocr keyword={keyword!r} variants={list(variant_names)!r} texts={[item['text'] for item in candidates]}")
    best = _pick_best_text_match(candidates, keyword)
    if best is None:
        print(f"[vision_bot] local_text_ocr no_match keyword={keyword!r}")
        return None
    print(
        f"[vision_bot] local_text_ocr match keyword={keyword!r} text={best['text']!r} "
        f"score={best['score']:.3f} center={best['center']} variant={best.get('variant')}"
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


def _number_keyboard_template(name: str) -> str:
    return f"assets/android/keyboard/number/{name}.png"


def _tap_number_keyboard_key(key: str, threshold: Optional[float] = None) -> Dict[str, Any]:
    key_name = str(key)
    if key_name not in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "delete", "confirm"):
        raise RuntimeError(f"不支持的数字键盘按键: {key_name}")
    template_path = _number_keyboard_template(key_name)
    img_bgr = screenshot_bgr()
    matched = match_once(img_bgr, template_path, threshold=threshold)
    if matched is None:
        raise RuntimeError(f"数字键盘模板匹配失败: {template_path}")
    top_left, confidence = matched
    tap_pt = tap_matched_center(template_path, top_left)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    return {
        "key": key_name,
        "template": template_path,
        "confidence": float(confidence),
        "tap": tap_pt,
    }


def _input_with_number_keyboard(value: int, clear_times: int = 6) -> Dict[str, Any]:
    text = str(int(value))
    if not text.isdigit():
        raise RuntimeError(f"数字键盘仅支持纯数字输入: {text!r}")
    threshold = botconfig.ANDROID_MATCH_THRESHOLD
    clear_results = []
    for _ in range(max(0, int(clear_times))):
        clear_results.append(_tap_number_keyboard_key("delete", threshold=threshold))
    digit_results = []
    for ch in text:
        digit_results.append(_tap_number_keyboard_key(ch, threshold=threshold))
    confirm_result = _tap_number_keyboard_key("confirm", threshold=threshold)
    return {
        "value": text,
        "clear_taps": [item["tap"] for item in clear_results],
        "digit_taps": [item["tap"] for item in digit_results],
        "confirm_tap": confirm_result["tap"],
    }


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
    map_button_tpl = str(matched_map_btn["template"])
    map_button_conf = float(matched_map_btn["confidence"])
    tap_map_button = tap_matched_center(map_button_tpl, matched_map_btn["top_left"])
    time.sleep(step_sleep_s)
    tap_x = tap_template(tpl_map_x, threshold=thr_map_x)
    time.sleep(step_sleep_s)
    input_x = _input_with_number_keyboard(int(x))
    time.sleep(step_sleep_s)
    tap_y = tap_template(tpl_map_y, threshold=thr_map_y)
    time.sleep(step_sleep_s)
    input_y = _input_with_number_keyboard(int(y))
    time.sleep(step_sleep_s)

    tap_go = tap_template(tpl_map_go, threshold=thr_map_go)
    arrival = wait_until_arrived_by_coord()
    tap_exit = None
    exit_error = None
    if bool(arrival.get("arrived")):
        try:
            tap_exit = tap_template(botconfig.ANDROID_TPL_MAP_EXIT, threshold=botconfig.ANDROID_MATCH_THRESHOLD)
        except Exception as e:
            exit_error = str(e)

    print(
        f"[vision_bot] navigate_to_coord target=({int(x)}, {int(y)}) "
        f"map_button={map_button_tpl} map_button_conf={map_button_conf:.3f} "
        f"tap_map_button={tap_map_button} tap_x={tap_x} input_x={input_x} tap_y={tap_y} input_y={input_y} tap_go={tap_go} "
        f"arrived={bool(arrival.get('arrived'))} coord={arrival.get('coord')} samples={arrival.get('samples')} "
        f"tap_map_exit={tap_exit} tap_map_exit_error={exit_error}"
    )
    return {
        "ok": True,
        "target": (int(x), int(y)),
        "arrived": bool(arrival.get("arrived")),
        "coord": arrival.get("coord"),
        "samples": arrival.get("samples"),
    }


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
    roi = parse_roi(roi_text, botconfig.KEY_ANDROID_COORD_ROI)
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
    roi = parse_roi(botconfig.MHXY_MAP_ROI, botconfig.KEY_MHXY_MAP_ROI)
    img_bgr = screenshot_bgr()
    png_bytes = _crop_png_bytes(img_bgr, roi)
    sys_util.save_debug_image(img_bgr[roi[1]:roi[3], roi[0]:roi[2]], "android_map_roi_cropped")
    ocr_result = run_local_ocr(png_bytes, use_det=True, use_cls=False, use_rec=True, log_prefix="[vision_bot]")
    map_name = flatten_ocr_text(ocr_result.get("result"))
    print(f"[vision_bot] current_map raw_text={map_name!r}")
    return {"map_name": map_name, "raw_ocr": ocr_result, "roi": list(roi)}

# botconfig.init()
# _input_with_number_keyboard(124)