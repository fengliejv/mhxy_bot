import os
from desk_util import VirtualKey
import desk_util
import sys_util
import sys
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, List
import cv2
import numpy as np
from siliflow_client import siliconflow_paddleocr
from image_matcher import TemplateMatcher
import ocr_util

def go_to_changan(hwnd: int = None) -> None:
    result = ocr_util.detect_current_map_by_roi(hwnd=hwnd)
    map_name = str(result.get("map_name", "")).strip()
    
    if "长安城" in map_name:
        return 

    desk_util.press_vk(VirtualKey.F8)
    desk_util.press_vk(VirtualKey.TAB)




    img = desk_util.capture_mhxy_client_image(hwnd)

    template_path = "assets/dituguangquan_0_6.PNG"
    matcher = TemplateMatcher(threshold=0.6)
    template_img = matcher.load_image(template_path)

    locations = matcher.match_all_templates(img, template_img)
    if not locations:
        raise RuntimeError("未匹配到地图光圈模板")

    (x, y), confidence = max(locations, key=lambda item: (item[0][1], item[0][0]))
    w = int(template_img.shape[1])
    h = int(template_img.shape[0])
    click_x = int(x + w - 1)
    click_y = int(y + h - 1)

    desk_util.click_at(hwnd, click_x, click_y)

    result["did_action"] = True
    return 

def main():
    hwnd = desk_util.init_mhxy_window()
    result = go_to_changan(hwnd=hwnd)
    for k, v in result.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()


