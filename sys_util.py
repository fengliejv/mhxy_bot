from __future__ import annotations

import ctypes
import os
import struct
import zlib
from binascii import crc32
from typing import Optional


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32


SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]


def load_dotenv(path: str) -> None:
    """
    从 .env 文件加载环境变量（仅当变量尚未在 os.environ 中存在时才写入）。

    - 支持形如 KEY=VALUE 的行
    - 会忽略空行、# 注释行
    - VALUE 会去掉首尾空格，并剥离一层单/双引号
    """
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        return


def set_dpi_aware() -> None:
    """
    将当前进程设置为 DPI aware（高分屏感知），减少 Windows 缩放导致的坐标偏差问题。

    用于：窗口坐标、截图 ROI、点击坐标等都按“真实像素”工作。
    """
    try:
        user32.SetProcessDPIAware()
    except Exception:
        return


def _enum_windows() -> list[int]:
    hwnds: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            hwnds.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc, 0)
    return hwnds


def _get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def find_window_by_title_substring(title_substring: str) -> int:
    """
    通过“窗口标题包含某个子串”来查找窗口句柄（hwnd）。

    返回：
    - 找到：hwnd（>0）
    - 未找到：0
    """
    needle = (title_substring or "").strip()
    if not needle:
        raise ValueError("title_substring 不能为空")
    for hwnd in _enum_windows():
        title = _get_window_text(hwnd)
        if needle in title:
            return hwnd
    return 0


def activate_window(hwnd: int) -> None:
    """
    尝试恢复并激活窗口到前台。

    说明：
    - Windows 对“强制抢焦点”有限制，这里使用 topmost 切换 + AttachThreadInput 的组合提高成功率。
    """
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

    current_thread = kernel32.GetCurrentThreadId()
    fg_hwnd = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

    if fg_thread and fg_thread != current_thread:
        user32.AttachThreadInput(fg_thread, current_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(fg_thread, current_thread, False)
    else:
        user32.SetForegroundWindow(hwnd)


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """
    获取窗口在屏幕坐标系下的矩形范围（left, top, right, bottom）。
    """
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("GetWindowRect 失败")
    return rect.left, rect.top, rect.right, rect.bottom


def _capture_screen_rect(left: int, top: int, right: int, bottom: int) -> tuple[int, int, bytes]:
    """
    截取屏幕中的矩形区域，返回 (width, height, bgra_bytes)。

    注意：
    - 这里是从“屏幕”拷贝像素，如果窗口被遮挡，结果会包含遮挡内容。
    - bgra_bytes 是 32 位 BGRA，按行从上到下排列。
    """
    width = int(right - left)
    height = int(bottom - top)
    if width <= 0 or height <= 0:
        raise ValueError("截图区域宽高非法")

    hdc_screen = user32.GetDC(0)
    if not hdc_screen:
        raise OSError("GetDC(0) 失败")
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    if not hdc_mem:
        user32.ReleaseDC(0, hdc_screen)
        raise OSError("CreateCompatibleDC 失败")

    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    if not hbmp:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        raise OSError("CreateCompatibleBitmap 失败")

    old = gdi32.SelectObject(hdc_mem, hbmp)
    try:
        if not gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, 0x00CC0020):
            raise OSError("BitBlt 失败（窗口可能被遮挡/最小化/权限限制）")

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bmi.bmiHeader.biSizeImage = width * height * 4

        buf_size = width * height * 4
        pixel_buf = (ctypes.c_ubyte * buf_size)()
        scanlines = gdi32.GetDIBits(hdc_mem, hbmp, 0, height, ctypes.byref(pixel_buf), ctypes.byref(bmi), 0)
        if scanlines != height:
            raise OSError("GetDIBits 失败")
        return width, height, bytes(pixel_buf)
    finally:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)


def save_bmp_32bgra(path: str, width: int, height: int, bgra: bytes) -> None:
    """
    将 32 位 BGRA 像素数据保存为 BMP 文件。
    """
    if len(bgra) != width * height * 4:
        raise ValueError("像素数据长度不匹配")

    file_header_size = 14
    info_header_size = 40
    pixel_offset = file_header_size + info_header_size
    file_size = pixel_offset + len(bgra)

    bfType = b"BM"
    bfSize = file_size
    bfReserved1 = 0
    bfReserved2 = 0
    bfOffBits = pixel_offset
    bmp_file_header = struct.pack("<2sIHHI", bfType, bfSize, bfReserved1, bfReserved2, bfOffBits)

    biSize = info_header_size
    biWidth = width
    biHeight = -height
    biPlanes = 1
    biBitCount = 32
    biCompression = 0
    biSizeImage = len(bgra)
    biXPelsPerMeter = 0
    biYPelsPerMeter = 0
    biClrUsed = 0
    biClrImportant = 0
    bmp_info_header = struct.pack(
        "<IiiHHIIiiII",
        biSize,
        biWidth,
        biHeight,
        biPlanes,
        biBitCount,
        biCompression,
        biSizeImage,
        biXPelsPerMeter,
        biYPelsPerMeter,
        biClrUsed,
        biClrImportant,
    )

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(bmp_file_header)
        f.write(bmp_info_header)
        f.write(bgra)


def save_png_32bgra(path: str, width: int, height: int, bgra: bytes) -> None:
    """
    将 32 位 BGRA 像素数据保存为 PNG 文件（RGBA，8bit，lossless）。
    """
    if len(bgra) != width * height * 4:
        raise ValueError("像素数据长度不匹配")

    def pack_u32_be(v: int) -> bytes:
        return bytes([(v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255])

    def chunk(ctype: bytes, data: bytes) -> bytes:
        return pack_u32_be(len(data)) + ctype + data + pack_u32_be(crc32(ctype + data) & 0xFFFFFFFF)

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        row = bgra[y * stride : (y + 1) * stride]
        for x in range(width):
            b = row[x * 4 + 0]
            g = row[x * 4 + 1]
            r = row[x * 4 + 2]
            a = row[x * 4 + 3]
            raw.extend((r, g, b, a))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = pack_u32_be(width) + pack_u32_be(height) + bytes([8, 6, 0, 0, 0])
    idat = zlib.compress(bytes(raw), level=6)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def capture_bgra(hwnd: int, roi: Optional[tuple[int, int, int, int]] = None) -> tuple[int, int, bytes]:
    """
    截图（基于窗口位置从屏幕拷贝像素），返回 (width, height, bgra_bytes)。

    - roi=None：截取整个窗口矩形
    - roi=(x1,y1,x2,y2)：截取窗口内 ROI（窗口左上角为原点，x2/y2 为右下角坐标，不包含边界点）
    """
    left, top, right, bottom = get_window_rect(hwnd)
    if roi is None:
        return _capture_screen_rect(left, top, right, bottom)
    x1, y1, x2, y2 = roi
    w = int(max(1, x2 - x1))
    h = int(max(1, y2 - y1))
    return _capture_screen_rect(left + x1, top + y1, left + x1 + w, top + y1 + h)


def capture_bmp(hwnd: int, out_path: str, roi: Optional[tuple[int, int, int, int]] = None) -> None:
    """
    截图并保存为 BMP（32 位 BGRA）。
    """
    w, h, bgra = capture_bgra(hwnd, roi=roi)
    save_bmp_32bgra(out_path, w, h, bgra)


def capture_png(hwnd: int, out_path: str, roi: Optional[tuple[int, int, int, int]] = None) -> None:
    """
    截图并保存为 PNG（RGBA，8bit，lossless）。
    """
    w, h, bgra = capture_bgra(hwnd, roi=roi)
    save_png_32bgra(out_path, w, h, bgra)


def _send_inputs(inputs: list[INPUT]) -> None:
    n = len(inputs)
    if n <= 0:
        return
    arr = (INPUT * n)(*inputs)
    sent = user32.SendInput(n, arr, ctypes.sizeof(INPUT))
    if sent != n:
        raise OSError("SendInput 失败")


def key_tap(vk: int) -> None:
    """
    发送一次键盘按键（按下+抬起）。

    vk: Windows Virtual-Key Code，例如 Tab=0x09, F8=0x77。
    """
    extra = ctypes.c_ulong(0)
    down = INPUT(
        type=INPUT_KEYBOARD,
        union=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=ctypes.pointer(extra))),
    )
    up = INPUT(
        type=INPUT_KEYBOARD,
        union=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=ctypes.pointer(extra))),
    )
    _send_inputs([down, up])


def _screen_metrics() -> tuple[int, int]:
    w = int(user32.GetSystemMetrics(0))
    h = int(user32.GetSystemMetrics(1))
    return w, h


def _to_absolute_mouse_xy(x: int, y: int) -> tuple[int, int]:
    sw, sh = _screen_metrics()
    ax = int(x * 65535 / max(sw - 1, 1))
    ay = int(y * 65535 / max(sh - 1, 1))
    return ax, ay


def mouse_left_click_screen(x: int, y: int) -> None:
    """
    在“屏幕坐标系”下移动鼠标并左键单击。
    """
    extra = ctypes.c_ulong(0)
    ax, ay = _to_absolute_mouse_xy(int(x), int(y))
    move = INPUT(
        type=INPUT_MOUSE,
        union=_INPUT_UNION(
            mi=MOUSEINPUT(dx=ax, dy=ay, mouseData=0, dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, time=0, dwExtraInfo=ctypes.pointer(extra))
        ),
    )
    down = INPUT(
        type=INPUT_MOUSE,
        union=_INPUT_UNION(mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN, time=0, dwExtraInfo=ctypes.pointer(extra))),
    )
    up = INPUT(
        type=INPUT_MOUSE,
        union=_INPUT_UNION(mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP, time=0, dwExtraInfo=ctypes.pointer(extra))),
    )
    _send_inputs([move, down, up])


def click_in_window(hwnd: int, xy: tuple[int, int]) -> None:
    """
    在“窗口左上角为原点”的坐标系下点击。

    xy: (x, y) 相对窗口左上角的偏移（像素）。
    """
    left, top, _, _ = get_window_rect(hwnd)
    x, y = xy
    mouse_left_click_screen(left + int(x), top + int(y))
