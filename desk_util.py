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
def _rest(ms: int = 500) -> None:
    """休息 ms 秒 + 0.5 秒 * 随机值（0~1）"""
    t = ms / 1000.0
    time.sleep(t + t * random.random())
    
def _set_dpi_aware() -> None:
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        print("SetProcessDpiAwarenessContext")
        return
    except Exception:
        pass
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2)
        print("SetProcessDpiAwareness")
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
        print("SetProcessDPIAware")
    except Exception:
        pass

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
    """
    通过窗口句柄截图，自动去掉标题栏和边框（只截客户区）
    :param hwnd: 窗口句柄
    :return: PIL Image 对象
    """
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    client_left, client_top = win32gui.ClientToScreen(hwnd, (left, top))
    client_right, client_bottom = win32gui.ClientToScreen(hwnd, (right, bottom))

    w = client_right - client_left
    h = client_bottom - client_top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)

    saveDC.BitBlt(
        (0, 0),
        (w, h),
        mfcDC,
        (left, top),
        win32con.SRCCOPY,
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

    # 6. 清理资源（必须）
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    return img_bgr


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

class _INPUT_union(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_union),
    ]

class VirtualKey(IntEnum):
    """Windows 虚拟键码枚举"""
    F8 = 0x77
    TAB = 0x09

def press_vk(vk: int) -> None:
    # 模拟按键：按下 vk →（可选）按住 hold_ms 毫秒 → 松开 vk
    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows")
    user32 = ctypes.windll.user32

    INPUT_KEYBOARD = 1  # SendInput 的输入类型：键盘
    KEYEVENTF_KEYUP = 0x0002  # 标记本次事件是“抬起键”
    KEYEVENTF_SCANCODE = 0x0008  # 以扫描码方式发送（比直接 vk 更接近底层输入）

    extra = _ULONG_PTR(0)  # dwExtraInfo，通常填 0 即可
    # 把虚拟键码 vk 映射为扫描码 scan（硬件键位码），并截取低 8 位
    scan = user32.MapVirtualKeyW(int(vk), 0) & 0xFF
    # 构造“按下键”的 INPUT 结构（wVk=0，使用 scan + KEYEVENTF_SCANCODE）
    down = _INPUT(type=INPUT_KEYBOARD, u=_INPUT_union(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE, 0, extra)))
    up = _INPUT(
        type=INPUT_KEYBOARD,
        # 构造“抬起键”的 INPUT 结构（同样使用 scan，并叠加 KEYEVENTF_KEYUP）
        u=_INPUT_union(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, extra)),
    )

    # 先发送“按下键”；成功返回值应为 1（表示成功注入了 1 个输入事件）
    sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(_INPUT))
    if sent != 1:
        # 兼容回退：某些环境 SendInput 失败时，用老 API keybd_event 兜底
        user32.keybd_event(int(vk), int(scan), 0, 0)

    _rest()
    # 再发送“抬起键”
    sent = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_INPUT))
    if sent != 1:
        user32.keybd_event(int(vk), int(scan), KEYEVENTF_KEYUP, 0)
    _rest()

def click_at(hwnd: int, click_x: int, click_y: int) -> None:
    # 鼠标移动到该点并左键点击
    user32 = ctypes.windll.user32
    # 将窗口客户区坐标转为屏幕坐标
    point = wintypes.POINT(click_x, click_y)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    # 设置鼠标位置
    user32.SetCursorPos(point.x, point.y)
    # 左键按下
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    _rest(100)
    img_bgr = capture_mhxy_client_image(hwnd)
    sys_util.save_debug_image(img_bgr,"move")

    # 左键抬起
    user32.mouse_event(0x0004, 0, 0, 0, 0)
