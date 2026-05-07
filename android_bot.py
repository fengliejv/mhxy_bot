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

        self.tpl_map_button = os.getenv("ANDROID_TPL_MAP_BUTTON", "").strip()
        self.tpl_coord_input = os.getenv("ANDROID_TPL_COORD_INPUT", "").strip()
        self.tpl_move_button = os.getenv("ANDROID_TPL_MOVE_BUTTON", "").strip()

        if not self.tpl_map_button:
            self.tpl_map_button = os.path.join("assets", "android_map_button.png")
        if not self.tpl_coord_input:
            self.tpl_coord_input = os.path.join("assets", "android_coord_input.png")
        if not self.tpl_move_button:
            self.tpl_move_button = os.path.join("assets", "android_move_button.png")

        self.match_threshold = float(os.getenv("ANDROID_MATCH_THRESHOLD", "0.8").strip() or "0.8")

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
        self.adb.tap(cx, cy)
        return cx, cy

    def open_mini_map(self) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        return self._tap_template(img_bgr, self.tpl_map_button, extra_offset=(0, 0))

    def input_target_coord(self, x: int, y: int) -> Tuple[int, int, str]:
        img_bgr = self.screenshot_bgr()
        click_offset_x = int(os.getenv("ANDROID_INPUT_CLICK_OFFSET_X", "0") or "0")
        click_offset_y = int(os.getenv("ANDROID_INPUT_CLICK_OFFSET_Y", "0") or "0")
        tx, ty = self._tap_template(
            img_bgr,
            self.tpl_coord_input,
            extra_offset=(click_offset_x, click_offset_y),
        )
        time.sleep(float(os.getenv("ANDROID_AFTER_FOCUS_SLEEP_S", "0.3") or "0.3"))
        clear_n = int(os.getenv("ANDROID_INPUT_CLEAR_BACKSPACE_N", "0") or "0")
        for _ in range(max(0, clear_n)):
            self.adb.keyevent(67)
        fmt = os.getenv("ANDROID_COORD_TEXT_FORMAT", "({x},{y})")
        text = fmt.format(x=int(x), y=int(y))
        self.adb.input_text(text)
        return tx, ty, text

    def click_move(self) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        return self._tap_template(img_bgr, self.tpl_move_button, extra_offset=(0, 0))

    def go_to_in_changan(self, x: int, y: int) -> Dict:
        detected = self.detect_current_map()
        map_name = str(detected.get("map_name", "")).strip()
        if "长安城" not in map_name:
            return {"ok": False, "reason": "not_in_changan", "map_name": map_name, "detected": detected}

        mp = self.open_mini_map()
        time.sleep(float(os.getenv("ANDROID_AFTER_OPEN_MAP_SLEEP_S", "0.5") or "0.5"))
        ip = self.input_target_coord(x, y)
        time.sleep(float(os.getenv("ANDROID_AFTER_INPUT_SLEEP_S", "0.3") or "0.3"))
        mv = self.click_move()
        return {
            "ok": True,
            "map_name": map_name,
            "map_button_tap": mp,
            "input_tap": (ip[0], ip[1]),
            "input_text": ip[2],
            "move_button_tap": mv,
            "detected": detected,
        }


def main() -> None:
    sys_util.load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    args = ap.parse_args()
    bot = AndroidMhxyBot()
    result = bot.go_to_in_changan(args.x, args.y)
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
