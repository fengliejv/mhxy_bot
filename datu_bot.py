from desk_util import VirtualKey
import desk_util
from image_matcher import match_template
import ocr_util
import cv2
import time


def go_to_changan(hwnd: int = None) -> None:
    result = ocr_util.detect_current_map_by_roi(hwnd=hwnd)
    map_name = str(result.get("map_name", "")).strip()
    
    if "长安城" in map_name:
        return 

    desk_util.press_vk(VirtualKey.F8)
    desk_util.press_vk(VirtualKey.TAB)
    template_path = "assets/dituguangquan_0_6.PNG"
    desk_util.match_template_and_click(hwnd, template_path, threshold=0.6)

    desk_util.waite_charachter_stop(hwnd)
    
    # 关闭地图光圈窗口
    desk_util.press_vk(VirtualKey.TAB)
    template_path = "assets/dadituguangquan_0_6.PNG"
    desk_util.match_template_and_click(hwnd, template_path, threshold=0.6)
    desk_util.waite_charachter_stop(hwnd)
    return 

def go_hotel(hwnd: int = None) -> None:
    #打开地图
    desk_util.press_vk(VirtualKey.TAB)
    template_path = "assets/changan_hotel.PNG"
    desk_util.match_template_and_click(hwnd, template_path, threshold=0.6)
    desk_util.waite_charachter_stop(hwnd)


def main():
    hwnd = desk_util.init_mhxy_window()
    result = go_to_changan(hwnd=hwnd)
    for k, v in result.items():
        print(f"{k}: {v}")
    go_hotel(hwnd=hwnd)

if __name__ == "__main__":
    main()


