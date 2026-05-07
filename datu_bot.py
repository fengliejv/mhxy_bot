from desk_util import VirtualKey
import desk_util
from image_matcher import match_template
import ocr_util



def go_to_changan_hotel(hwnd: int = None) -> None:
    result = ocr_util.detect_current_map_by_roi(hwnd=hwnd)
    map_name = str(result.get("map_name", "")).strip()
    
    if "长安城" in map_name:
        go_hotel(hwnd=hwnd)
        return 

    desk_util.press_vk(VirtualKey.F8)
    desk_util.press_vk(VirtualKey.TAB)
    template_path = "assets/dituguangquan_0_6.PNG"
    desk_util.match_template_and_click(hwnd, template_path, threshold=0.6)

    desk_util.waite_charachter_stop(hwnd)

    
    # 关闭地图窗口
    desk_util.press_vk(VirtualKey.TAB)

    template_path = "assets/dadituguangquan_0_6.PNG"
    desk_util.match_template_and_click(hwnd, template_path, threshold=0.4, center=True)
    # desk_util.click_at(hwnd,template_path,0.6)
    desk_util.waite_charachter_stop(hwnd)
    go_hotel(hwnd=hwnd)

    return 

def go_hotel(hwnd: int = None) -> None:
    #打开地图
    desk_util.press_vk(VirtualKey.TAB)
    template_path = "assets/changan_jiudian_0.9.PNG"
    desk_util.match_template_and_click(hwnd, template_path, threshold=0.9, center=True)
    desk_util.waite_charachter_stop(hwnd)
    desk_util.press_vk(VirtualKey.TAB)



def main():
    hwnd = desk_util.init_mhxy_window()
    desk_util.move_mouse_to_window_center(hwnd)
    # go_to_changan_hotel(hwnd=hwnd)
    desk_util.move_with_map(hwnd,469,167)

    go_hotel(hwnd=hwnd)

if __name__ == "__main__":
    main()


