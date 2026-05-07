import argparse
import io
import os
import time
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

import siliflow_client
import sys_util
from adb_util import AdbClient
from image_matcher import match_template


def _parse_roi(roi_text: str) -> Tuple[int, int, int, int]:
    parts = [x.strip() for x in roi_text.split(",")]
    if len(parts) != 4:
        raise RuntimeError("MHXY_MAP_ROI 格式错误，期望 x1,y1,x2,y2")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError("MHXY_MAP_ROI 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("MHXY_MAP_ROI 数值无效，要求 x2>x1,y2>y1")
    return x1, y1, x2, y2


def _bgr_to_pil(img_bgr: np.ndarray) -> Image.Image:
    if img_bgr is None:
        raise RuntimeError("空图像")
    if len(img_bgr.shape) == 3 and img_bgr.shape[2] == 3:
        return Image.fromarray(img_bgr[:, :, ::-1])
    if len(img_bgr.shape) == 3 and img_bgr.shape[2] == 4:
        return Image.fromarray(img_bgr[:, :, [2, 1, 0, 3]])
    return Image.fromarray(img_bgr)


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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


class AndroidMhxyBot:
    def __init__(self, adb: Optional[AdbClient] = None) -> None:
        self.adb = adb or AdbClient()
        self.map_roi_text = os.getenv("MHXY_MAP_ROI", "").strip()
        if not self.map_roi_text:
            raise RuntimeError("缺少 MHXY_MAP_ROI，请在 .env 配置，例如 0,0,120,120")

        self.tpl_map_button = os.getenv("ANDROID_TPL_MAP_BUTTON", "assets/android/map/map_button.jpg").strip() or "assets/android/map/map_button.jpg"
        self.tpl_map_search_icon = os.getenv("ANDROID_TPL_MAP_SEARCH_ICON", "assets/android/map/map_search_icon.png").strip() or "assets/android/map/map_search_icon.png"
        self.tpl_map_input_icon = os.getenv("ANDROID_TPL_MAP_INPUT_ICON", "assets/android/map/map_input_icon.png").strip() or "assets/android/map/map_input_icon.png"
        self.tpl_map_dianxiaoer = os.getenv("ANDROID_TPL_MAP_DIANXIAOER", "assets/android/map/map_dianxiaoer.png").strip() or "assets/android/map/map_dianxiaoer.png"
        self.tpl_map_on_the_way = os.getenv("ANDROID_TPL_MAP_ON_THE_WAY", "assets/android/map/map_on_the_way.png").strip() or "assets/android/map/map_on_the_way.png"

        self.match_threshold = float(os.getenv("ANDROID_MATCH_THRESHOLD", "0.8").strip() or "0.8")
        self.step_sleep_s = float(os.getenv("ANDROID_STEP_SLEEP_S", "0.4").strip() or "0.4")

    def screenshot_bgr(self) -> np.ndarray:
        img = self.adb.screenshot_bgr()
        sys_util.save_debug_image(img, "android_screen_bgr")
        return img

    def detect_current_map(self) -> Dict:
        x1, y1, x2, y2 = _parse_roi(self.map_roi_text)
        img_bgr = self.screenshot_bgr()
        pil_img = _bgr_to_pil(img_bgr)
        cropped = pil_img.crop((x1, y1, x2, y2))
        sys_util.save_debug_image(cropped, "android_map_roi_cropped")
        png_bytes = _pil_to_png_bytes(cropped)
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        map_name = str(ocr_result.get("content", "")).strip()
        return {"map_name": map_name, "raw_ocr": ocr_result, "roi": [x1, y1, x2, y2]}

    def _match_once(self, img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None):
        thr = self.match_threshold if threshold is None else threshold
        ok, _, locations = match_template(img_bgr, template_path, threshold=thr, find_all=True)
        if not ok or not locations:
            return None
        return _pick_best_location(locations)

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

    def _tap(self, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        pt = self._tap_template(img_bgr, template_path, threshold=threshold, extra_offset=extra_offset)
        time.sleep(self.step_sleep_s)
        return pt

    def go_to_dianxiaoer_in_changan(self) -> Dict:
        detected = self.detect_current_map()
        map_name = str(detected.get("map_name", "")).strip()
        if "长安城" not in map_name:
            return {"ok": False, "reason": "not_in_changan", "map_name": map_name, "detected": detected}

        # thr_map_button = float(os.getenv("ANDROID_THR_MAP_BUTTON", str(self.match_threshold)) or self.match_threshold)
        thr_search_icon = float(os.getenv("ANDROID_THR_MAP_SEARCH_ICON", str(self.match_threshold)) or self.match_threshold)
        thr_input_icon = float(os.getenv("ANDROID_THR_MAP_INPUT_ICON", str(self.match_threshold)) or self.match_threshold)
        thr_dianxiaoer = float(os.getenv("ANDROID_THR_MAP_DIANXIAOER", str(self.match_threshold)) or self.match_threshold)
        thr_on_the_way = float(os.getenv("ANDROID_THR_MAP_ON_THE_WAY", str(self.match_threshold)) or self.match_threshold)

        p1 = self._tap(self.tpl_map_button, threshold=0.6)
        p2 = self._tap(self.tpl_map_search_icon, threshold=thr_search_icon)
        p3 = self._tap(self.tpl_map_input_icon, threshold=thr_input_icon)

        adb_ime = os.getenv("ANDROID_ADB_IME_ID", "com.android.adbkeyboard/.AdbIME").strip() or "com.android.adbkeyboard/.AdbIME"
        sogou_ime = os.getenv("ANDROID_SOGOU_IME_ID", "com.sohu.inputmethod.sogou.xiaomi/.SogouIME").strip() or "com.sohu.inputmethod.sogou.xiaomi/.SogouIME"
        self.adb.ime_set(adb_ime)
        time.sleep(self.step_sleep_s)
        self.adb.adbkeyboard_input_text("店小二")
        time.sleep(self.step_sleep_s)
        self.adb.keyevent(66)
        time.sleep(self.step_sleep_s)
        self.adb.ime_set(sogou_ime)
        time.sleep(self.step_sleep_s)

        p4 = self._tap(self.tpl_map_dianxiaoer, threshold=thr_dianxiaoer)
        p5 = self._tap(self.tpl_map_on_the_way, threshold=thr_on_the_way)

        return {
            "ok": True,
            "map_name": map_name,
            "tap_map_button": p1,
            "tap_search_icon": p2,
            "tap_input_icon": p3,
            "input_text": "店小二",
            "tap_dianxiaoer": p4,
            "tap_on_the_way": p5,
            "detected": detected,
        }


def main() -> None:
    sys_util.load_dotenv()

    bot = AndroidMhxyBot()
    result = bot.go_to_dianxiaoer_in_changan()
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
