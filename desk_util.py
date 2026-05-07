import ctypes
from ctypes import wintypes
import sys
import os
import sys_util
import win32gui
import win32ui
import win32con
from PIL import Image
from enum import IntEnum
import random
import time
import cv2
import numpy as np
import re
import ddddocr_util

def _rest(ms: int = 500) -> None:
    """休息 ms 秒 + 0.5 秒 * 随机值（0~1）"""
    t = ms / 1000.0
    time.sleep(t + t * random.random())
    
def _set_dpi_aware() -> None:
    user32 = ctypes.windll.user32
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    # ctypes.windll.shcore.SetProcessDpiAwareness(2)

def _find_window(title_substring: str) -> int:
    """
    通过遍历系统所有窗口，根据窗口标题（包含指定子串）来查找目标窗口的句柄 (HWND)。
    返回找到的窗口句柄整数值，如果没找到则返回 0。
    """
    if not title_substring:
        raise ValueError("title_substring 不能为空")
    user32 = ctypes.windll.user32
    found_hwnd = 0

    # 定义 EnumWindows 需要的回调函数类型
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _enum_proc(hwnd: int, lparam: int) -> bool:
        nonlocal found_hwnd
        # 如果已经找到了，返回 False 停止遍历
        if found_hwnd:
            return False
            
        # 跳过不可见的窗口
        if not user32.IsWindowVisible(hwnd):
            return True
            
        # 获取窗口标题长度，如果为 0 (无标题) 则跳过
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
            
        # 创建足够长的 Unicode 缓冲区来接收窗口标题
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        
        # 检查当前窗口标题是否包含我们想要的子串
        if title_substring in title:
            found_hwnd = int(hwnd)
            return False  # 找到目标，返回 False 结束 EnumWindows 遍历
            
        return True  # 没找到，返回 True 继续遍历下一个窗口

    # 调用 Windows API 遍历所有顶层窗口，将每个窗口句柄传给 _enum_proc
    user32.EnumWindows(EnumWindowsProc(_enum_proc), 0)
    
    return found_hwnd

def _activate_window(hwnd: int) -> None:
    """
    激活指定窗口，将其设置为前台窗口。
    """
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)

def init_mhxy_window() -> int:
    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows")
    sys_util.load_dotenv()
    _set_dpi_aware()
    # 获取目标窗口标题的子串，默认查找包含 "梦幻西游 ONLINE" 的窗口
    title_substring = os.getenv("MHXY_WINDOW_TITLE", "梦幻西游 ONLINE").strip()

    hwnd = _find_window(title_substring)
    if not hwnd:
        raise RuntimeError("未找到窗口：标题包含 {!r}".format(title_substring))
    _activate_window(hwnd)
    return int(hwnd)




def capture_mhxy_client_image(
    hwnd: int,
):
    _set_dpi_aware()
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        if not win32gui.IsWindowVisible(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    except Exception:
        pass
    try:
        _activate_window(hwnd)
    except Exception:
        pass
    _rest(120)

    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    client_left, client_top = win32gui.ClientToScreen(hwnd, (left, top))

    w = right - left
    h = bottom - top
    if w <= 0 or h <= 0:
        _rest(120)
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        w = right - left
        h = bottom - top
        if w <= 0 or h <= 0:
            raise RuntimeError("客户端区域尺寸无效")

    screenDC = win32gui.GetDC(0)
    mfcDC = win32ui.CreateDCFromHandle(screenDC)
    saveDC = mfcDC.CreateCompatibleDC()

    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)

    saveDC.BitBlt(
        (0, 0),
        (w, h),
        mfcDC,
        (client_left, client_top),
        win32con.SRCCOPY | 0x40000000,
    )

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = Image.frombuffer(
        "RGB",
        (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
        bmpstr,
        "raw",
        "BGRX",
        0,
        1,
    )

    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(0, screenDC)
    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    return img_bgr


try:
    _ULONG_PTR = wintypes.ULONG_PTR  # 指针宽度的无符号整数类型（32 位=32bit，64 位=64bit）
except AttributeError:
    # 某些 Python/ctypes 版本未提供 wintypes.ULONG_PTR，用 size_t 做兼容兜底（同为指针宽度）
    _ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    # 对应 Win32 的 KEYBDINPUT 结构体：描述一次键盘输入事件
    _fields_ = [
        ("wVk", wintypes.WORD),  # 虚拟键码（使用扫描码发送时通常填 0）
        ("wScan", wintypes.WORD),  # 扫描码（硬件键位码）
        ("dwFlags", wintypes.DWORD),  # 标志位：KEYEVENTF_SCANCODE/KEYEVENTF_KEYUP 等
        ("time", wintypes.DWORD),  # 事件时间戳（0 表示系统自行填充）
        ("dwExtraInfo", _ULONG_PTR),  # 额外信息（指针宽度）
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    # 对应 Win32 的 BITMAPINFOHEADER：描述位图像素格式与尺寸
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
    # 对应 Win32 的 BITMAPINFO：BITMAPINFOHEADER + 调色板/颜色表（这里仅占位）
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class _INPUT_union(ctypes.Union):
    # 对应 Win32 的 INPUT 联合体：这里只用到键盘 ki 分支
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    # 对应 Win32 的 INPUT 结构体：type 指明输入类型，u 指向具体联合体数据
    _fields_ = [
        ("type", wintypes.DWORD),  # INPUT_KEYBOARD=1
        ("u", _INPUT_union),  # 具体输入数据（键盘/鼠标/硬件）
    ]

class VirtualKey(IntEnum):
    """Windows 虚拟键码枚举"""
    F8 = 0x77
    TAB = 0x09

def press_vk(vk: int) -> None:
    # 模拟按键：按下 vk → 松开 vk
    _rest()

    user32 = ctypes.windll.user32

    INPUT_KEYBOARD = 1  # INPUT.type：键盘输入
    KEYEVENTF_KEYUP = 0x0002  # KEYBDINPUT.dwFlags：按键抬起
    KEYEVENTF_SCANCODE = 0x0008  # KEYBDINPUT.dwFlags：使用扫描码而非虚拟键码

    extra = _ULONG_PTR(0)  # KEYBDINPUT.dwExtraInfo：通常填 0
    # vk -> scan：将虚拟键码映射为扫描码（更接近真实硬件按键事件）
    scan = user32.MapVirtualKeyW(int(vk), 0) & 0xFF
    # 构造“按下键”事件：wVk=0，配合 KEYEVENTF_SCANCODE 表示以扫描码发送
    down = _INPUT(type=INPUT_KEYBOARD, u=_INPUT_union(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE, 0, extra)))
    up = _INPUT(
        type=INPUT_KEYBOARD,
        # 构造“抬起键”事件：扫描码 + KEYEVENTF_KEYUP
        u=_INPUT_union(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, extra)),
    )

    # 发送“按下键”。成功时返回 1（表示注入了 1 个输入事件）
    sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(_INPUT))
    if sent != 1:
        # 兜底：SendInput 失败时用旧 API keybd_event（用虚拟键码触发）
        user32.keybd_event(int(vk), int(scan), 0, 0)

    # 留一点间隔，避免按下/抬起过快导致游戏漏读
    _rest()
    # 发送“抬起键”
    sent = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_INPUT))
    if sent != 1:
        user32.keybd_event(int(vk), int(scan), KEYEVENTF_KEYUP, 0)
    # 再留一点间隔，减少连发干扰
    _rest()
import win32api
import win32con
import image_matcher
import pyautogui
def match_template_and_click(hwnd: int, template_path: str,threshold: float, center: bool = False) -> None:
    img_bgr = capture_mhxy_client_image(hwnd)

    cursor_template_path = "assets/shubiao.PNG"
    cursor_ok, _, cursor_locations = image_matcher.match_template(
        img_bgr,
        cursor_template_path,
        threshold=0.5,
        find_all=False,
    )
    if (not cursor_ok) or (not cursor_locations):
        raise RuntimeError("未匹配到鼠标模板: {}".format(cursor_template_path))

    target_ok, _, target_locations = image_matcher.match_template(
        img_bgr,
        template_path,
        threshold=threshold,
        find_all=False,
    )
    if (not target_ok) or (not target_locations):
        print("未匹配到目标模板: {}".format(template_path))
        return

    (cursor_x, cursor_y), _ = cursor_locations[0]
    (target_x, target_y), _ = target_locations[0]
    # 取目标模板中心点
    target_img = cv2.imread(template_path)
    if target_img is None:
        raise RuntimeError("无法读取目标模板图片: {}".format(template_path))
    h, w = target_img.shape[:2]
    target_cx = target_x 
    target_cy = target_y
    if center:
        target_cx = target_x + w // 2
        target_cy = target_y + h // 2

    target_img = cv2.imread(template_path)
    if target_img is None:
        raise RuntimeError("无法读取目标模板图片: {}".format(template_path))
    cursor_pos = pyautogui.position()
    cursor_pos_x, cursor_pos_y = cursor_pos[0], cursor_pos[1]

    print(f"cursor_x: {cursor_x}, cursor_y: {cursor_y}")
    print(f"target_cx: {target_cx}, target_cy: {target_cy}")
    print(f"cursor position: {cursor_pos}")
    x = target_cx+(cursor_pos_x-cursor_x)
    y = target_cy+(cursor_pos_y-cursor_y)
    print(f"x: {x}, y: {y}")
    pyautogui.moveTo(x, y, 1)
    pyautogui.click()


def waite_charachter_stop(hwnd: int):
    roi_text = os.getenv("MHXY_CHARACTER_COORD_ROI", "").strip()
    if not roi_text:
        raise RuntimeError("缺少角色坐标 ROI 环境变量 MHXY_CHARACTER_COORD_ROI（格式：(x1,y1,x2,y2)）")

    roi_text = roi_text.strip().strip("()（）").replace("，", ",")
    parts = [x.strip() for x in roi_text.split(",") if x.strip()]
    if len(parts) != 4:
        raise RuntimeError("角色坐标 ROI 格式错误，期望 (x1,y1,x2,y2)")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError("角色坐标 ROI 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("角色坐标 ROI 数值无效，要求 x2>x1,y2>y1")
    roi_box = (x1, y1, x2, y2)

    def _normalize(s: str) -> str:
        raw = str(s or "").strip()
        nums = re.findall(r"\d+", raw)
        if len(nums) >= 2:
            return f"{int(nums[0])},{int(nums[1])}"
        if len(nums) == 1:
            return str(int(nums[0]))
        return raw

    prev = None
    stable = 0
    while True:
        _rest(1500)
        img_bgr = capture_mhxy_client_image(hwnd)
        coord_text = _normalize(ddddocr_util.ocr_region(img_bgr, roi_box))
        sys_util.save_debug_image(img_bgr, f"waite_charachter_stop_{coord_text}")
        print(coord_text)
        if coord_text and coord_text == prev:
            stable += 1
        else:
            stable = 1
        prev = coord_text
        if stable >= 2:
            return coord_text


from siliflow_client import paddleocr
def move_with_map(hwnd:int,target_x:int,target_y:int) -> None:
    """
    移动鼠标到地图上的指定位置
    """
    move_mouse_to_window_center(hwnd)
    press_vk(VirtualKey.TAB)
    _rest(300)

    cursor_template_path = "assets/shubiao.PNG"
    roi_w = 60
    roi_h = 60

    def _parse_coord(text: str):
        raw = str(text or "").strip()
        nums = re.findall(r"\d+", raw)
        if len(nums) < 2:
            return None
        x = int(nums[0])
        y = int(nums[1])
        if x >= 1000:
            x = int(str(x)[-3:])
        if y >= 1000:
            y = int(str(y)[-3:])
        return x, y

    def _detect_cursor_and_coord():
        img_bgr = capture_mhxy_client_image(hwnd)
        ok, _, locations = image_matcher.match_template(
            img_bgr,
            cursor_template_path,
            threshold=0.35,
            find_all=False,
        )
        if (not ok) or (not locations):
            return None, None, None
        (cx, cy), _ = locations[0]
        anchor_x = int(cx)
        anchor_y = int(cy)

        x1 = int(anchor_x - roi_w//2)
        x2 = int(anchor_x + roi_w//2)
        y2 = int(anchor_y + roi_h//2)
        y1 = int(anchor_y - roi_h//2)

        h, w = img_bgr.shape[:2]
        if x1 < 0:
            x1 = 0
        if y1 < 0:
            y1 = 0
        if x2 > w:
            x2 = w
        if y2 > h:
            y2 = h
        if x2 <= x1 or y2 <= y1:
            return None, None, None
        roi = img_bgr[y1:y2, x1:x2]
        text = paddleocr(roi)
        coord = _parse_coord(text)
        return coord, (x1, y1, x2, y2), (cx, cy)

    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    client_w = int(right - left)
    client_h = int(bottom - top)

    def _clamp(v: int, lo: int, hi: int) -> int:
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    def _estimate_px_per_unit(axis: str, probe_px: int) -> float:
        coord0, _, _ = _detect_cursor_and_coord()
        if coord0 is None:
            return 0.0
        x0, y0 = coord0
        if axis == "x":
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(probe_px), 0, 0, 0)
        else:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, int(probe_px), 0, 0)
        _rest(160)
        coord1, _, _ = _detect_cursor_and_coord()
        if axis == "x":
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(-probe_px), 0, 0, 0)
        else:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, int(-probe_px), 0, 0)
        _rest(160)
        if coord1 is None:
            return 0.0
        x1, y1 = coord1
        delta_units = abs(int(x1) - int(x0)) if axis == "x" else abs(int(y1) - int(y0))
        if delta_units <= 0:
            return 0.0
        return float(abs(int(probe_px))) / float(delta_units)

    step_x = None
    step_y = None
    prev_sign_x = None
    prev_sign_y = None
    max_iter = 60
    for _ in range(max_iter):
        coord, _, _ = _detect_cursor_and_coord()
        if coord is None:
            _rest(200)
            continue

        cur_map_x, cur_map_y = coord
        if step_x is None or step_y is None:
            probe_px_x = _clamp(client_w // 4 if client_w > 0 else 160, 80, 240)
            probe_px_y = _clamp(client_h // 4 if client_h > 0 else 120, 60, 200)
            px_per_unit_x = _estimate_px_per_unit("x", probe_px_x)
            px_per_unit_y = _estimate_px_per_unit("y", probe_px_y)

            err_units_x = abs(int(target_x) - int(cur_map_x))
            err_units_y = abs(int(target_y) - int(cur_map_y))

            if px_per_unit_x <= 0.0:
                step_x = _clamp(err_units_x * 8, 40, 800)
            else:
                step_x = _clamp(int(round(err_units_x * px_per_unit_x)), 40, 1200)

            if px_per_unit_y <= 0.0:
                step_y = _clamp(err_units_y * 8, 40, 800)
            else:
                step_y = _clamp(int(round(err_units_y * px_per_unit_y)), 40, 1200)

        if int(cur_map_x) == int(target_x) and int(cur_map_y) == int(target_y):
            return

        move_dx = 0
        move_dy = 0

        if int(cur_map_x) != int(target_x):
            sign_x = 1 if int(cur_map_x) < int(target_x) else -1
            if prev_sign_x is not None and sign_x != prev_sign_x:
                step_x = max(1, step_x // 2)
            move_dx = int(sign_x * step_x)
            prev_sign_x = sign_x

        if int(cur_map_y) != int(target_y):
            sign_y = 1 if int(cur_map_y) < int(target_y) else -1
            if prev_sign_y is not None and sign_y != prev_sign_y:
                step_y = max(1, step_y // 2)
            move_dy = int(sign_y * step_y)
            prev_sign_y = sign_y

        if move_dx == 0 and move_dy == 0:
            return

        pyautogui.moveRel(move_dx, move_dy, duration=0.05)
        _rest(120)

    raise RuntimeError("move_with_map 未在迭代次数内收敛到目标坐标: {},{}".format(target_x, target_y))


def move_mouse_to_window_center(hwnd: int) -> None:
    """
    将鼠标移动到指定窗口的客户区中央
    """
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (center_x, center_y))

    # 获取当前鼠标位置
    curr_x, curr_y = win32gui.GetCursorPos()

    # 计算相对移动量
    dx = screen_x - curr_x
    dy = screen_y - curr_y

    # 使用 mouse_event 移动鼠标
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)
