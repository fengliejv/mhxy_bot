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

    img_bgr = desk_util.capture_mhxy_client_image(hwnd)

    template_path = "assets/dituguangquan_0_6.PNG"
    

    success, _, locations = match_template(
        img_bgr,
        template_path,
        threshold=0.6,
        find_all=True,
    )
    if (not success) or (not locations):
        raise RuntimeError("未匹配到地图光圈模板")

    (x, y), confidence = max(locations, key=lambda item: (item[0][1], item[0][0]))
    template_img = cv2.imread(template_path)
    if template_img is None:
        raise RuntimeError("无法读取模板图片: {}".format(template_path))
    w = int(template_img.shape[1])
    h = int(template_img.shape[0])
    click_x = int(x + w - 1)
    click_y = int(y + h - 1)

    desk_util.click_at(hwnd, click_x, click_y)

    result["did_action"] = True
    result["match_result"] = {
        "template_path": template_path,
        "threshold": 0.6,
        "selected": ((int(x), int(y)), float(confidence)),
        "locations": [((int(px), int(py)), float(conf)) for (px, py), conf in locations],
        "template_wh": (w, h),
    }
    result["clicked"] = (click_x, click_y)
    return result

def main():
    hwnd = desk_util.init_mhxy_window()
    result = go_to_changan(hwnd=hwnd)
    for k, v in result.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()


