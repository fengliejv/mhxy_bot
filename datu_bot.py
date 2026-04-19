import os
import sys
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, List
import cv2
import numpy as np
from siliflow_client import siliconflow_paddleocr
from image_matcher import TemplateMatcher


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def _set_dpi_aware() -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def _find_window_by_title_substring(title_substring: str) -> int:
    user32 = ctypes.windll.user32
    found_hwnd = 0

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _enum_proc(hwnd: int, lparam: int) -> bool:
        nonlocal found_hwnd
        if found_hwnd:
            return False
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title_substring in title:
            found_hwnd = int(hwnd)
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(_enum_proc), 0)
    return found_hwnd


def activate_mhxy_window(title_substring: Optional[str] = None) -> int:
    """
    激活(置前)《梦幻西游 ONLINE》窗口。
    title_substring 为空时，默认读取环境变量 MHXY_WINDOW_TITLE。
    返回 hwnd；找不到窗口时抛异常。
    """
    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows")

    _set_dpi_aware()
    _load_dotenv()
    title_substring = (title_substring or os.getenv("MHXY_WINDOW_TITLE", "")).strip()
    if not title_substring:
        raise RuntimeError("缺少窗口标题子串：请设置 MHXY_WINDOW_TITLE 或传入 title_substring")

    hwnd = _find_window_by_title_substring(title_substring)
    if not hwnd:
        raise RuntimeError("未找到窗口：标题包含 {!r}".format(title_substring))

    user32 = ctypes.windll.user32
    SW_RESTORE = 9

    user32.ShowWindow(hwnd, SW_RESTORE)

    fg_hwnd = user32.GetForegroundWindow()
    kernel32 = ctypes.windll.kernel32
    current_thread = kernel32.GetCurrentThreadId()
    fg_pid = wintypes.DWORD()
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(fg_pid))

    if fg_thread != current_thread:
        user32.AttachThreadInput(fg_thread, current_thread, True)
        try:
            user32.SetForegroundWindow(hwnd)
        finally:
            user32.AttachThreadInput(fg_thread, current_thread, False)
    else:
        user32.SetForegroundWindow(hwnd)

    user32.BringWindowToTop(hwnd)
    return int(hwnd)


def _bring_hwnd_to_foreground(hwnd: int) -> int:
    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows")
    _set_dpi_aware()

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    SW_RESTORE = 9
    user32.ShowWindow(int(hwnd), SW_RESTORE)

    fg_hwnd = user32.GetForegroundWindow()
    current_thread = kernel32.GetCurrentThreadId()
    fg_pid = wintypes.DWORD()
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(fg_pid))

    if fg_thread != current_thread:
        user32.AttachThreadInput(fg_thread, current_thread, True)
        try:
            user32.SetForegroundWindow(int(hwnd))
        finally:
            user32.AttachThreadInput(fg_thread, current_thread, False)
    else:
        user32.SetForegroundWindow(int(hwnd))

    user32.BringWindowToTop(int(hwnd))
    return int(hwnd)


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def _capture_client_bgra(hwnd: int):
    _set_dpi_aware()
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("获取客户端区域失败")

    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        raise RuntimeError("客户端区域尺寸无效")

    pt = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        raise RuntimeError("ClientToScreen 失败")

    hdc_screen = user32.GetDC(0)
    if not hdc_screen:
        raise RuntimeError("获取屏幕DC失败")

    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    if not hdc_mem:
        user32.ReleaseDC(0, hdc_screen)
        raise RuntimeError("创建兼容DC失败")

    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    if not hbmp:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        raise RuntimeError("创建兼容位图失败")

    old_obj = gdi32.SelectObject(hdc_mem, hbmp)
    SRCCOPY = 0x00CC0020
    CAPTUREBLT = 0x40000000

    try:
        if not gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, pt.x, pt.y, SRCCOPY | CAPTUREBLT):
            raise RuntimeError("BitBlt 抓图失败")

        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bmi.bmiHeader.biSizeImage = width * height * 4

        buf = (ctypes.c_ubyte * (width * height * 4))()
        DIB_RGB_COLORS = 0
        copied = gdi32.GetDIBits(
            hdc_mem,
            hbmp,
            0,
            height,
            ctypes.byref(buf),
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
        )
        if copied == 0:
            raise RuntimeError("GetDIBits 读取像素失败")
        return width, height, bytes(buf)
    finally:
        gdi32.SelectObject(hdc_mem, old_obj)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)


try:
    _ULONG_PTR = wintypes.ULONG_PTR
except AttributeError:
    _ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _INPUT_union(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_union),
    ]


def _press_vk(vk: int, *, hold_ms: int = 0) -> None:
    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows")
    user32 = ctypes.windll.user32

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008

    extra = _ULONG_PTR(0)
    scan = user32.MapVirtualKeyW(int(vk), 0) & 0xFF
    down = _INPUT(type=INPUT_KEYBOARD, u=_INPUT_union(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE, 0, extra)))
    up = _INPUT(
        type=INPUT_KEYBOARD,
        u=_INPUT_union(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, extra)),
    )

    sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(_INPUT))
    if sent != 1:
        user32.keybd_event(int(vk), int(scan), 0, 0)
    if hold_ms > 0:
        time.sleep(max(hold_ms, 0) / 1000.0)
    sent = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_INPUT))
    if sent != 1:
        user32.keybd_event(int(vk), int(scan), KEYEVENTF_KEYUP, 0)


def capture_mhxy_client_image(
    hwnd: int,
    is_debug: bool = False,
    debug_dir: str = "debug_shots",
):
    """
    抓取指定 hwnd 的客户端正文区域（不含标题栏/边框）。
    is_debug=True 时保存图片到 debug_dir，并返回保存路径。

    返回: (image_bgr, saved_path, hwnd)
    """
    width, height, bgra = _capture_client_bgra(hwnd)

    image = np.frombuffer(bgra, dtype=np.uint8).reshape((height, width, 4))
    image_bgr = image[:, :, :3].copy()

    saved_path = None
    if is_debug:
        os.makedirs(debug_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        saved_path = os.path.abspath(os.path.join(debug_dir, "mhxy_client_{}.png".format(ts)))
        if not cv2.imwrite(saved_path, image_bgr):
            raise RuntimeError("保存调试图片失败: {}".format(saved_path))

    return image_bgr, saved_path, hwnd


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


def detect_current_map_by_roi(
    is_debug: bool = False,
    hwnd: int = None,
) -> dict:
    """
    激活窗口后，在 MHXY_MAP_ROI 指定区域调用 paddleocr 识别当前地图文字。
    返回：
        {
            "map_name": str,
            "ocr_items": list,
            "roi": [x1,y1,x2,y2],
            "roi_saved_path": str|None,
            "window_hwnd": int
        }
    """
    _load_dotenv()
    roi_text = os.getenv("MHXY_MAP_ROI", "").strip()
    if not roi_text:
        raise RuntimeError("缺少 MHXY_MAP_ROI，请在 .env 配置，例如 0,0,120,120")
    x1, y1, x2, y2 = _parse_roi(roi_text)

    image_bgr, _, hwnd = capture_mhxy_client_image(hwnd, is_debug=is_debug)
    img_h, img_w = image_bgr.shape[:2]
    if x2 > img_w or y2 > img_h:
        raise RuntimeError("MHXY_MAP_ROI 超出截图范围，截图尺寸={}x{}".format(img_w, img_h))

    roi_img = image_bgr[y1:y2, x1:x2]
    ok, enc = cv2.imencode(".png", roi_img)
    if not ok:
        raise RuntimeError("ROI 编码失败")

    roi_saved_path = None
    if is_debug:
        os.makedirs("debug_shots", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        roi_saved_path = os.path.abspath(os.path.join("debug_shots", "mhxy_map_roi_{}.png".format(ts)))
        if not cv2.imwrite(roi_saved_path, roi_img):
            raise RuntimeError("保存 ROI 调试图片失败: {}".format(roi_saved_path))

    ocr_result = siliconflow_paddleocr(enc.tobytes())
    map_name = str(ocr_result.get("content", "")).strip()

    return {
        "map_name": map_name,
        "roi": [x1, y1, x2, y2],
        "roi_saved_path": roi_saved_path,
        "window_hwnd": hwnd,
        "raw_ocr": ocr_result,
    }


def go_to_changan(
    *,
    is_debug: bool = False,
    hwnd: int = None,
    wait_after_f8_s: float = 1.2,
    wait_after_tab_s: float = 0.8,
) -> dict:
    if hwnd is None:
        hwnd = activate_mhxy_window()
    else:
        hwnd = _bring_hwnd_to_foreground(hwnd)
        time.sleep(0.1)

    result = detect_current_map_by_roi(is_debug=is_debug, hwnd=hwnd)
    map_name = str(result.get("map_name", "")).strip()
    print(f"当前地图文字: {map_name}")
    if "长安城" in map_name:
        result["did_action"] = False
        return result

    VK_F8 = 0x77
    VK_TAB = 0x09

    _press_vk(VK_F8)
    if wait_after_f8_s > 0:
        time.sleep(float(wait_after_f8_s))
    _press_vk(VK_TAB)
    if wait_after_tab_s > 0:
        time.sleep(float(wait_after_tab_s))
    image_bgr, _, _ = capture_mhxy_client_image(hwnd, is_debug=is_debug)

    template_path = "assets/dituguangquan_0_6.PNG"
    matcher = TemplateMatcher(method="ccoeff_normed", threshold=0.6)
    template_img = matcher.load_image(template_path)
    if template_img is None:
        raise RuntimeError("无法读取模板图片: {}".format(template_path))

    locations = matcher.match_all_templates(image_bgr, template_img)
    if not locations:
        raise RuntimeError("未匹配到地图光圈模板")

    (x, y), confidence = max(locations, key=lambda item: (item[0][1], item[0][0]))
    w = int(template_img.shape[1])
    h = int(template_img.shape[0])
    click_x = int(x + w - 1)
    click_y = int(y + h - 1)

    # 截图保存
    shot_path = None
    if is_debug:
        os.makedirs("debug_shots", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        shot_path = os.path.abspath(os.path.join("debug_shots", f"match_roi_{ts}.png"))
        roi = image_bgr[y:y + h, x:x + w]
        cv2.imwrite(shot_path, roi)

    # 鼠标移动到该点并左键点击
    user32 = ctypes.windll.user32
    # 将窗口客户区坐标转为屏幕坐标
    point = wintypes.POINT(click_x, click_y)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    # 设置鼠标位置
    user32.SetCursorPos(point.x, point.y)
    # 左键按下
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    # 左键抬起
    user32.mouse_event(0x0004, 0, 0, 0, 0)

    result["did_action"] = True
    out = dict(result)
    out.update(
        {
            "clicked": (click_x, click_y),
            "match_result": {
                "template_path": template_path,
                "threshold": 0.6,
                "selected": ((int(x), int(y)), float(confidence)),
                "locations": [((int(px), int(py)), float(conf)) for (px, py), conf in locations],
                "template_wh": (w, h),
            },
            "debug_shot": shot_path,
        }
    )
    return out

       



if __name__ == "__main__":
    hwnd = activate_mhxy_window()
    result = go_to_changan(is_debug=True,hwnd=hwnd)
    for k, v in result.items():
        print(f"{k}: {v}")


