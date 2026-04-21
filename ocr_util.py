import os
import io
import desk_util
import siliflow_client
import datetime
from PIL import Image
import sys_util
def _parse_roi(roi_text: str):
    parts = [x.strip() for x in roi_text.split(",")]
    if len(parts) != 4:
        raise RuntimeError("MHXY_MAP_ROI 格式错误，期望 x1,y1,x2,y2")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError("MHXY_MAP_ROI 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("MHXY_MAP_ROI 数值无效，要求 x2>x1,y2>y1")
    return x1, y1, x2, y2

def detect_current_map_by_roi(
    hwnd: int = None,
) -> dict:
    """
    在 MHXY_MAP_ROI 指定区域调用 paddleocr 识别当前地图文字。
    返回：
        {
            "map_name": str,
            "ocr_items": list,
            "roi": [x1,y1,x2,y2],
            "roi_saved_path": str|None,
            "window_hwnd": int
        }
    """
    roi_text = os.getenv("MHXY_MAP_ROI", "").strip()
    if not roi_text:
        raise RuntimeError("缺少 MHXY_MAP_ROI，请在 .env 配置，例如 0,0,120,120")
    x1, y1, x2, y2 = _parse_roi(roi_text)

    img_bgr = desk_util.capture_mhxy_client_image(hwnd)
    sys_util.save_debug_image(img_bgr, "map_roi")

    # 根据 ROI 裁剪图像
    if isinstance(img_bgr, (bytes, bytearray, memoryview)):
        img = Image.open(io.BytesIO(bytes(img_bgr)))
    else:
        shape = getattr(img_bgr, "shape", None)
        if shape is not None and len(shape) == 3 and shape[2] == 3:
            img = Image.fromarray(img_bgr[:, :, ::-1])
        elif shape is not None and len(shape) == 3 and shape[2] == 4:
            img = Image.fromarray(img_bgr[:, :, [2, 1, 0, 3]])
        else:
            img = Image.fromarray(img_bgr)
    cropped_img = img.crop((x1, y1, x2, y2))
    sys_util.save_debug_image(cropped_img, "map_roi_cropped")

    if isinstance(cropped_img, (bytes, bytearray, memoryview)):
        img_input = bytes(cropped_img)
    else:
        buf = io.BytesIO()
        cropped_img.save(buf, format="PNG")
        img_input = buf.getvalue()

    ocr_result = siliflow_client.siliconflow_paddleocr(img_input)
    map_name = str(ocr_result.get("content", "")).strip()
    print("OCR 结果:", ocr_result)
    print("地图名称:", map_name)
    return {
        "map_name": map_name,
        "raw_ocr": ocr_result,
    }



