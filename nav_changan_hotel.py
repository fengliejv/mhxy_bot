from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zlib

import sys_util


VK_TAB = 0x09
VK_F8 = 0x77


def _extract_first_json_object(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
        s = s.strip()
    start = s.find("{")
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return ""





def _parse_int_list(v: str, n: int) -> tuple[int, ...]:
    parts = [p.strip() for p in (v or "").split(",") if p.strip() != ""]


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None or v == "" else v


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return default if v is None or v == "" else int(v)


def _env_xy(name: str, default_xy: tuple[int, int]) -> tuple[int, int]:
    v = os.environ.get(name)
    if v is None or v == "":
        return default_xy
    x, y = _parse_int_list(v, 2)
    return int(x), int(y)


def _env_roi(name: str, default_roi: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    v = os.environ.get(name)
    if v is None or v == "":
        return default_roi
    x1, y1, x2, y2 = _parse_int_list(v, 4)
    return int(x1), int(y1), int(x2), int(y2)


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v == "":
        return bool(default)
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _safe_name(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "unknown"
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]+", "", s)
    return s[:40] if len(s) > 40 else s


def bgra_to_png_bytes(width: int, height: int, bgra: bytes) -> bytes:
    if len(bgra) != width * height * 4:
        raise ValueError("像素数据长度不匹配")

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

    def chunk(ctype: bytes, data: bytes) -> bytes:
        return struct_pack_u32(len(data)) + ctype + data + struct_pack_u32(zlib.crc32(ctype + data) & 0xFFFFFFFF)

    def struct_pack_u32(v: int) -> bytes:
        return bytes([(v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255])

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct_pack_u32(width) + struct_pack_u32(height) + bytes([8, 6, 0, 0, 0])
    idat = zlib.compress(bytes(raw), level=6)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def siliconflow_ocr_text(png_bytes: bytes) -> str:
    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 SILICONFLOW_API_KEY（请在 .env 或环境变量中配置）")

    base_url = _env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
    model = _env("SILICONFLOW_OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.5")
    url = base_url + "/chat/completions"

    b64 = base64.b64encode(png_bytes).decode("ascii")
    data_url = "data:image/png;base64," + b64

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请只输出图片中的地图名（例如：长安城/大唐官府），不要输出其它内容。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"OCR 请求失败: HTTP {getattr(e, 'code', '?')}: {body}") from e
    except Exception as e:
        raise RuntimeError(f"OCR 请求失败: {e}") from e

    try:
        j = json.loads(body)
        content = j["choices"][0]["message"]["content"]
        return (content or "").strip()
    except Exception as e:
        raise RuntimeError(f"OCR 响应解析失败: {body[:500]}") from e


def siliconflow_locate_jiu(png_bytes: bytes) -> tuple[int, int, str] | None:
    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 SILICONFLOW_API_KEY（请在 .env 或环境变量中配置）")

    base_url = _env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
    model = _env("SILICONFLOW_OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.5")
    url = base_url + "/chat/completions"

    b64 = base64.b64encode(png_bytes).decode("ascii")
    data_url = "data:image/png;base64," + b64

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请在图片中找到包含“酒”的文字（优先匹配：酒店/酒馆/茶酒/酒）。"
                        "只输出一个 JSON 对象：{\"x\":<数字>,\"y\":<数字>,\"text\":<字符串>}，"
                        "其中 x,y 为该文字中心点像素坐标（以图片左上角为(0,0)，x向右，y向下）。"
                        "如果找不到，输出 null。",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"定位请求失败: HTTP {getattr(e, 'code', '?')}: {body}") from e
    except Exception as e:
        raise RuntimeError(f"定位请求失败: {e}") from e

    try:
        j = json.loads(body)
        content = (j["choices"][0]["message"]["content"] or "").strip()
        if content == "null":
            return None
        obj_s = _extract_first_json_object(content)
        if not obj_s:
            return None
        obj = json.loads(obj_s)
        x = int(float(obj.get("x")))
        y = int(float(obj.get("y")))
        t = str(obj.get("text") or "")
        return x, y, t
    except Exception:
        return None


def read_map_name_from_roi(hwnd: int, roi: tuple[int, int, int, int]) -> str:
    w, h, bgra = sys_util.capture_bgra(hwnd, roi=roi)
    png_bytes = bgra_to_png_bytes(w, h, bgra)
    return siliconflow_ocr_text(png_bytes)


def find_changan_hotel_click_point(hwnd: int) -> tuple[int, int] | None:
    roi_s = os.environ.get("MHXY_HOTEL_OCR_ROI", "").strip()
    roi = None
    if roi_s:
        try:
            x1, y1, x2, y2 = _parse_int_list(roi_s, 4)
            roi = (int(x1), int(y1), int(x2), int(y2))
        except Exception:
            roi = None

    w, h, bgra = sys_util.capture_bgra(hwnd, roi=roi)
    png_bytes = bgra_to_png_bytes(w, h, bgra)
    found = siliconflow_locate_jiu(png_bytes)
    if not found:
        return None

    x, y, text = found
    y_offset = int(float(_env("MHXY_JIU_CLICK_Y_OFFSET", "10")))
    x = int(max(0, min(w - 1, x)))
    y = int(max(0, min(h - 1, y + y_offset)))

    if roi is not None:
        x += int(roi[0])
        y += int(roi[1])
    log(f"OCR 定位到“{text}”，点击点(相对窗口): ({x},{y})")
    return x, y


def nav_changan_hotel() -> None:
    sys_util.set_dpi_aware()
    sys_util.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    title = _env("MHXY_WINDOW_TITLE", "梦幻西游 ONLINE")
    roi = _env_roi("MHXY_MAP_ROI", (30, 100, 120, 120))
    click_changan = _env_xy("MHXY_CLICK_CHANGAN", (720, 425))
    click_enter_hotel = _env_xy("MHXY_CLICK_ENTER_CHANGAN_HOTEL", (500, 10))
    click_datang = _env_xy("MHXY_CLICK_DATANG", (720, 620))
    click_enter = _env_xy("MHXY_CLICK_ENTER_CHANGAN", (920, 650))
    enter_delay = float(_env("MHXY_ENTER_CHANGAN_DELAY", "5"))
    after_enter_delay = float(_env("MHXY_AFTER_ENTER_CHANGAN_DELAY", "2"))
    after_click_changan_hotel_delay = float(_env("MHXY_AFTER_CLICK_CHANGAN_HOTEL_DELAY", "5"))
    step_delay_ms = _env_int("MHXY_STEP_DELAY_MS", 150)
    step_delay = max(0.0, step_delay_ms / 1000.0)
    shots_root = _env("MHXY_DEBUG_DIR", "debug_shots").strip()
    save_shots = _env_bool("MHXY_SAVE_STEP_SCREENSHOTS", True)
    save_roi = _env_bool("MHXY_SAVE_ROI_SCREENSHOTS", True)

    run_dir = ""
    if save_shots or save_roi:
        ts = time.strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.abspath(os.path.join(shots_root, f"nav_changan_hotel_{ts}"))
        os.makedirs(run_dir, exist_ok=True)
        log(f"截图目录: {run_dir}")

    hwnd = sys_util.find_window_by_title_substring(title)
    if not hwnd:
        raise RuntimeError(f"未找到窗口：标题包含 {title!r}")
    log(f"找到窗口: {title!r} hwnd={hwnd}")
    sys_util.activate_window(hwnd)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "01_activated.png"))

    log(f"捕获地图 ROI: {roi}")
    if save_roi and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "02_map_roi.png"), roi=roi)
    map_name = read_map_name_from_roi(hwnd, roi)
    log(f"OCR 地图识别: {map_name!r}")
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, f"03_after_ocr_{_safe_name(map_name)}.png"))
    if "长安城" in map_name:
        log("当前在长安城：按 Tab 打开小地图")
        sys_util.key_tap(VK_TAB)
        time.sleep(1)
        if save_shots and run_dir:
            sys_util.capture_png(hwnd, os.path.join(run_dir, "04_tab_open_map.png"))
        click_pt = find_changan_hotel_click_point(hwnd)
        if click_pt is None:
            log(f"未定位到“酒”，回退到配置坐标: {click_changan}")
            click_pt = click_changan
        log(f"点击长安酒店(定位): {click_pt}")
        sys_util.click_in_window(hwnd, click_pt)
        time.sleep(step_delay)
        if save_shots and run_dir:
            sys_util.capture_png(hwnd, os.path.join(run_dir, "05_click_changan_hotel.png"))
        log(f"点击长安酒店后等待: {after_click_changan_hotel_delay} 秒")
        time.sleep(max(0.0, after_click_changan_hotel_delay))
        if save_shots and run_dir:
            sys_util.capture_png(hwnd, os.path.join(run_dir, "05b_after_wait_enter_hotel.png"))
        log(f"点击进入长安酒店坐标: {click_enter_hotel}")
        sys_util.click_in_window(hwnd, click_enter_hotel)
        time.sleep(step_delay)
        if save_shots and run_dir:
            sys_util.capture_png(hwnd, os.path.join(run_dir, "05c_click_enter_hotel.png"))
        return

    log("不在长安城：按 F8 回到大唐官府")
    sys_util.key_tap(VK_F8)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "04_f8_back_datang.png"))
    log("按 Tab 打开小地图")
    sys_util.key_tap(VK_TAB)
    time.sleep(step_delay)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "05_tab_open_map.png"))
    log(f"点击前往长安入口坐标: {click_datang}")
    sys_util.click_in_window(hwnd, click_datang)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "06_click_go_changan.png"))
    log(f"等待进入长安城: {enter_delay} 秒")
    time.sleep(max(0.0, enter_delay))
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "07_after_wait.png"))
    log(f"点击进入长安城坐标: {click_enter}")
    sys_util.click_in_window(hwnd, click_enter)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "08_click_enter_changan.png"))
    log(f"进入长安城后等待: {after_enter_delay} 秒")
    time.sleep(max(0.0, after_enter_delay))
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "08b_after_enter_wait.png"))
    log("进入后按 Tab 打开小地图")
    sys_util.key_tap(VK_TAB)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "09_tab_open_map_in_changan.png"))
    click_pt = find_changan_hotel_click_point(hwnd)
    if click_pt is None:
        log(f"未定位到“酒”，回退到配置坐标: {click_changan}")
        click_pt = click_changan
    log(f"点击长安酒店(定位): {click_pt}")
    sys_util.click_in_window(hwnd, click_pt)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "10_click_changan_hotel.png"))
    log(f"点击长安酒店后等待: {after_click_changan_hotel_delay} 秒")
    time.sleep(max(0.0, after_click_changan_hotel_delay))
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "10b_after_wait_enter_hotel.png"))
    log(f"点击进入长安酒店坐标: {click_enter_hotel}")
    sys_util.click_in_window(hwnd, click_enter_hotel)
    time.sleep(step_delay)
    if save_shots and run_dir:
        sys_util.capture_png(hwnd, os.path.join(run_dir, "10c_click_enter_hotel.png"))


def main() -> int:
    try:
        nav_changan_hotel()
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
