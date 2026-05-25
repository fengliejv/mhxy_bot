import os
import threading
from typing import Optional, Sequence

_lock = threading.Lock()
_dotenv_loaded = False
_dotenv_path = ".env"

KEY_DEBUG = "DEBUG"
KEY_ADB_PATH = "ADB_PATH"
KEY_ADB_SERIAL = "ADB_SERIAL"
KEY_ANDROID_SCREENSHOT_BACKEND = "ANDROID_SCREENSHOT_BACKEND"
KEY_ANDROID_SCRCPY_MAX_FPS = "ANDROID_SCRCPY_MAX_FPS"
KEY_ANDROID_SCRCPY_BITRATE = "ANDROID_SCRCPY_BITRATE"
KEY_ANDROID_SCRCPY_MAX_WIDTH = "ANDROID_SCRCPY_MAX_WIDTH"
KEY_ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS = "ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS"
KEY_MINERU_CMD = "MINERU_CMD"
KEY_MHXY_MAP_ROI = "MHXY_MAP_ROI"
KEY_ANDROID_COORD_ROI = "ANDROID_COORD_ROI"
KEY_BATTLE_CALCULATION_ROI = "BATTLE_CALCULATION_ROI"
KEY_ANDROID_MATCH_THRESHOLD = "ANDROID_MATCH_THRESHOLD"
KEY_ANDROID_STEP_SLEEP_S = "ANDROID_STEP_SLEEP_S"
KEY_ANDROID_STEP_SLEEP_S_WORD_PUZZLE = "ANDROID_STEP_SLEEP_S_WORD_PUZZLE"

KEY_ANDROID_ADB_IME_ID = "ANDROID_ADB_IME_ID"
KEY_ANDROID_SOGOU_IME_ID = "ANDROID_SOGOU_IME_ID"

KEY_ANDROID_ARRIVAL_MAX_WAIT_S = "ANDROID_ARRIVAL_MAX_WAIT_S"
KEY_ANDROID_ARRIVAL_CHECK_INTERVAL_S = "ANDROID_ARRIVAL_CHECK_INTERVAL_S"
KEY_ANDROID_ARRIVAL_STABLE_COUNT = "ANDROID_ARRIVAL_STABLE_COUNT"

KEY_SILICONFLOW_API_KEY = "SILICONFLOW_API_KEY"
KEY_SILICONFLOW_BASE_URL = "SILICONFLOW_BASE_URL"
KEY_SILICONFLOW_OCR_MODEL = "SILICONFLOW_OCR_MODEL"
KEY_SILICONFLOW_QWEN_MODEL = "SILICONFLOW_QWEN_MODEL"
KEY_SILICONFLOW_ENABLE_THINKING = "SILICONFLOW_ENABLE_THINKING"
KEY_SILICONFLOW_TIMEOUT_S = "SILICONFLOW_TIMEOUT_S"

ADB_PATH = "adb"
ANDROID_SCREENSHOT_BACKEND = "auto"
ANDROID_SCRCPY_MAX_FPS = 15
ANDROID_SCRCPY_BITRATE = 8000000
ANDROID_SCRCPY_MAX_WIDTH = 0
ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS = 3000

ANDROID_MATCH_THRESHOLD = 0.4
ANDROID_STEP_SLEEP_S = 0.5
ANDROID_STEP_SLEEP_S_WORD_PUZZLE = 0.25

ANDROID_THR_MAP_BUTTON = 0.5
ANDROID_THR_MAP_X = ANDROID_MATCH_THRESHOLD
ANDROID_THR_MAP_Y = ANDROID_MATCH_THRESHOLD
ANDROID_THR_MAP_GO = ANDROID_MATCH_THRESHOLD

ANDROID_ADB_IME_ID = "com.android.adbkeyboard/.AdbIME"
ANDROID_SOGOU_IME_ID = "com.sohu.inputmethod.sogou.xiaomi/.SogouIME"

ANDROID_ARRIVAL_MAX_WAIT_S = 120.0
ANDROID_ARRIVAL_CHECK_INTERVAL_S = 0.5
ANDROID_ARRIVAL_STABLE_COUNT = 2

ANDROID_THR_MENU_DAOJU = 0.7
ANDROID_THR_PROP_FEIXINGFU = ANDROID_MATCH_THRESHOLD
ANDROID_THR_PROP_USE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_FEIXINGFU_MAP = ANDROID_MATCH_THRESHOLD
ANDROID_THR_DAOJU_CLOSE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_TRANSFER = ANDROID_MATCH_THRESHOLD
ANDROID_TRANSFER_RETRY = 10
ANDROID_TRANSFER_RETRY_SLEEP_S = ANDROID_STEP_SLEEP_S

ANDROID_THR_SYSTEM_CLOSE_GUIDE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_CLOSE_TASK = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_HIDE_DIALOG = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_EXPAND = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_HIDE_UI_DISABLE = 0.95
ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE = 0.95
ANDROID_THR_SYSTEM_BACK = ANDROID_MATCH_THRESHOLD

ANDROID_THR_PROP_CHANGAN_FLAG = ANDROID_MATCH_THRESHOLD
ANDROID_THR_MAP_TELEPORT_POINT = 0.6
ANDROID_TELEPORT_TARGET_X = 1640
ANDROID_TELEPORT_TARGET_Y = 500

ANDROID_THR_BAOTU_RECEIVE_TASK = ANDROID_MATCH_THRESHOLD
ANDROID_THR_NPC_XIAOER = 0.55
ANDROID_THR_CHANGAN_HOTEL_DOOR = 0.3

MHXY_MAP_ROI = "270,30,430,80"
ANDROID_COORD_ROI = "249,82,418,127"
BATTLE_CALCULATION_ROI = "100, 100, 200, 200"

ANDROID_TPL_MAP_BUTTON = "assets/android/map/map_button.jpg"
ANDROID_TPL_MAP_BUTTON_2 = "assets/android/map/map_button2.png"
ANDROID_TPL_MAP_SEARCH_ICON = "assets/android/map/map_search_icon.png"
ANDROID_TPL_MAP_INPUT_ICON = "assets/android/map/map_input_icon.png"
ANDROID_TPL_MAP_GO = "assets/android/map/map_go.jpg"
ANDROID_TPL_MAP_EXIT = "assets/android/map/map_exit.jpg"
ANDROID_TPL_MAP_DIANXIAOER = "assets/android/map/map_dianxiaoer.png"
ANDROID_TPL_MAP_ON_THE_WAY = "assets/android/map/map_on_the_way.png"
ANDROID_TPL_MENU_DAOJU = "assets/android/memu/daoju.png"
ANDROID_TPL_PROP_FEIXINGFU = "assets/android/daoju/feixingfu.png"
ANDROID_TPL_PROP_CHANGAN_FLAG = "assets/android/daoju/changandaobiaoqi.png"
ANDROID_TPL_PROP_USE = "assets/android/daoju/jiemian/shiyong.png"
ANDROID_TPL_DAOJU_CLOSE = "assets/android/daoju/jiemian/guanbi.png"
ANDROID_TPL_FEIXINGFU_MAP_AOLAIGUO = "assets/android/map/feixingfuditu/aolaiguo.png"
ANDROID_TPL_FEIXINGFU_MAP_BAOXIANGGUO = "assets/android/map/feixingfuditu/baoxiangguo.png"
ANDROID_TPL_FEIXINGFU_MAP_CHANGANCHENG = "assets/android/map/feixingfuditu/changancheng.png"
ANDROID_TPL_FEIXINGFU_MAP_CHANGSHOUCUN = "assets/android/map/feixingfuditu/changshoucun.png"
ANDROID_TPL_FEIXINGFU_MAP_JIANYECHENG = "assets/android/map/feixingfuditu/jianye.png"
ANDROID_TPL_FEIXINGFU_MAP_ZHUZIGUO = "assets/android/map/feixingfuditu/zhuziguo.png"
ANDROID_TPL_FEIXINGFU_MAP_XILIANGNVGUO = "assets/android/map/feixingfuditu/xilaingnvguo.png"
ANDROID_TPL_MAP_TELEPORT_POINT = "assets/android/map/daobiaoqiditu/chuansongdian.png"
ANDROID_TPL_BAOTU_RECEIVE_TASK = "assets/android/baotu/tingtingwufang.png"
ANDROID_TPL_BAOTU_ATTACK_TALK = "assets/android/baotu/woshilaishoushinide.png"
ANDROID_TPL_ZHAOHUANSHOU_QIANGDAO = "assets/android/zhaohuanshou/qiangdao.png"
ANDROID_TPL_CHANGAN_HOTEL_DOOR = "assets/android/changancheng/jiudianmenkou.png"
ANDROID_TPL_SYSTEM_CLOSE_GUIDE = "assets/android/system/guanbizhiyin.png"
ANDROID_TPL_SYSTEM_CLOSE_TASK = "assets/android/system/close_task.jpg"
ANDROID_TPL_SYSTEM_HIDE_DIALOG = "assets/android/system/yincangduihua.png"
ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK = "assets/android/system/zidonggongjisuoxiao.png"
ANDROID_TPL_SYSTEM_EXPAND = "assets/android/system/expand.jpg"
ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE = "assets/android/system/yincangjiemian_disable.png"
ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE = "assets/android/system/yincangwanjia_disable.png"
ANDROID_TPL_SYSTEM_BACK = "assets/android/system/back.png"
ANDROID_TPL_SYSTEM_TRANSFER = "assets/android/system/transfer.jpg"
ANDROID_TPL_NPC_DIANXIAOER_1 = "assets/android/npc/dianxiaoer1.png"
ANDROID_TPL_NPC_DIANXIAOER_2 = "assets/android/npc/dianxiaoer2.png"
ANDROID_TPL_NPC_DIANXIAOER_3 = "assets/android/npc/dianxiaoer3.png"
ANDROID_TPL_NPC_CHANGAN_YIZHANLAOBAN = "assets/android/npc/changanyizhanlaoban.png"
ANDROID_TPL_NPC_JIEYINXIANNV = "assets/android/npc/jieyinxiannv.png"
ANDROID_TPL_NPC_LAOXIA = "assets/android/npc/laoxia.png"
ANDROID_TPL_NPC_TIANJIANG = "assets/android/npc/tianjiang.png"
ANDROID_TPL_CHAT_WOYAOQU = "assets/android/chat/woyaoqu.png"

ZHUZI_TO_JINGWAI = "7,4"
JINGWAI_TO_SHITUO = "7,49"
JINGWAI_TO_MOWANG = "58,108"
JINGWAI_TO_WUZHUANG = "630,70"
JINGWAI_TO_PANSI = "547,107"
CHANGAN_TO_HUANSHENG = "1150,214"
CHANGAN_TO_JIANGNANYEWAI = "536,2"
CHANGAN_FLY_YIZHANLAOBAN = "1161, 784"
CHANGAN_FLY_JIUDIAN = "1634, 500"
CHANGAN_FLY_YEWAI = "1777, 882"
GUOJING_TO_DIFU = "52,324"
GUOJING_TO_PUTUO = "224,61"
GUOJING_TO_JINGWAI = "8,76"
JIANYE_TO_DONGHAIWAN = "242,129"
AOLAI_TO_NVER = "10,135"
AOLAI_TO_HUAGUO = "1150,214"
CHANGSHOU_TO_FANGCUN = "109,204"
CHANGSHOU_TO_CHANGSHOUJIAOWAI = "144,5"
DONGHAIWAN_TO_LONGGONG = "111,89"
CHANGSHOUJIAOWAI_TO_TIANGONG = "24,56"

MINERU_CMD = ""

SILICONFLOW_API_KEY = ""
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_OCR_MODEL = "PaddlePaddle/PaddleOCR-VL-1.5"
SILICONFLOW_QWEN_MODEL = "Pro/moonshotai/Kimi-K2.6"


def init(dotenv_path: str = ".env") -> None:
    global _dotenv_loaded, _dotenv_path
    p = str(dotenv_path or ".env").strip() or ".env"
    if _dotenv_loaded and p == _dotenv_path:
        return
    with _lock:
        if _dotenv_loaded and p == _dotenv_path:
            return
        _dotenv_path = p
        _load_dotenv(p)
        _dotenv_loaded = True


def _load_dotenv(path: str) -> None:
    if not path:
        return
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


def env_str(key: str, default: str = "") -> str:
    init()
    v = os.getenv(str(key), "")
    s = str(v or "").strip()
    if s:
        return s
    return str(default or "")


def env_optional_str(key: str) -> Optional[str]:
    init()
    s = str(os.getenv(str(key), "") or "").strip()
    return s or None


def env_str_first(keys: Sequence[str], default: str = "") -> str:
    for k in keys:
        v = env_str(str(k), "")
        if v:
            return v
    return str(default or "")


def env_int(key: str, default: int) -> int:
    s = env_str(key, "")
    if not s:
        return int(default)
    return int(s)


def env_float(key: str, default: float) -> float:
    s = env_str(key, "")
    if not s:
        return float(default)
    return float(s)


def env_bool(key: str, default: bool = False) -> bool:
    s = env_str(key, "")
    if not s:
        return bool(default)
    v = s.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def _bind_str(name: str, key: Optional[str] = None) -> None:
    globals()[name] = env_str(key or name, globals()[name])


def _bind_float(name: str, key: Optional[str] = None) -> None:
    globals()[name] = env_float(key or name, globals()[name])


def _bind_int(name: str, key: Optional[str] = None) -> None:
    globals()[name] = env_int(key or name, globals()[name])


def _bind_many(bindings: Sequence[tuple], binder) -> None:
    for name, key in bindings:
        binder(name, key)


STR_KEY_BINDINGS = (
    ("MHXY_MAP_ROI", KEY_MHXY_MAP_ROI),
    ("ANDROID_COORD_ROI", KEY_ANDROID_COORD_ROI),
    ("BATTLE_CALCULATION_ROI", KEY_BATTLE_CALCULATION_ROI),
    ("ADB_PATH", KEY_ADB_PATH),
    ("ANDROID_SCREENSHOT_BACKEND", KEY_ANDROID_SCREENSHOT_BACKEND),
    ("ANDROID_ADB_IME_ID", KEY_ANDROID_ADB_IME_ID),
    ("ANDROID_SOGOU_IME_ID", KEY_ANDROID_SOGOU_IME_ID),
    ("MINERU_CMD", KEY_MINERU_CMD),
    ("SILICONFLOW_API_KEY", KEY_SILICONFLOW_API_KEY),
    ("SILICONFLOW_BASE_URL", KEY_SILICONFLOW_BASE_URL),
    ("SILICONFLOW_OCR_MODEL", KEY_SILICONFLOW_OCR_MODEL),
    ("SILICONFLOW_QWEN_MODEL", KEY_SILICONFLOW_QWEN_MODEL),
)

STR_TEMPLATE_BINDINGS = (
    ("ANDROID_TPL_MAP_BUTTON", None),
    ("ANDROID_TPL_MAP_BUTTON_2", None),
    ("ANDROID_TPL_MAP_SEARCH_ICON", None),
    ("ANDROID_TPL_MAP_INPUT_ICON", None),
    ("ANDROID_TPL_MAP_GO", None),
    ("ANDROID_TPL_MAP_EXIT", None),
    ("ANDROID_TPL_MAP_DIANXIAOER", None),
    ("ANDROID_TPL_MAP_ON_THE_WAY", None),
    ("ANDROID_TPL_MENU_DAOJU", None),
    ("ANDROID_TPL_PROP_FEIXINGFU", None),
    ("ANDROID_TPL_PROP_CHANGAN_FLAG", None),
    ("ANDROID_TPL_PROP_USE", None),
    ("ANDROID_TPL_DAOJU_CLOSE", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_AOLAIGUO", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_BAOXIANGGUO", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_CHANGANCHENG", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_CHANGSHOUCUN", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_JIANYECHENG", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_ZHUZIGUO", None),
    ("ANDROID_TPL_FEIXINGFU_MAP_XILIANGNVGUO", None),
    ("ANDROID_TPL_MAP_TELEPORT_POINT", None),
    ("ANDROID_TPL_BAOTU_RECEIVE_TASK", None),
    ("ANDROID_TPL_BAOTU_ATTACK_TALK", None),
    ("ANDROID_TPL_ZHAOHUANSHOU_QIANGDAO", None),
    ("ANDROID_TPL_CHANGAN_HOTEL_DOOR", None),
    ("ANDROID_TPL_SYSTEM_CLOSE_GUIDE", None),
    ("ANDROID_TPL_SYSTEM_CLOSE_TASK", None),
    ("ANDROID_TPL_SYSTEM_HIDE_DIALOG", None),
    ("ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK", None),
    ("ANDROID_TPL_SYSTEM_EXPAND", None),
    ("ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE", None),
    ("ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE", None),
    ("ANDROID_TPL_SYSTEM_BACK", None),
    ("ANDROID_TPL_SYSTEM_TRANSFER", None),
    ("ANDROID_TPL_NPC_DIANXIAOER_1", None),
    ("ANDROID_TPL_NPC_DIANXIAOER_2", None),
    ("ANDROID_TPL_NPC_DIANXIAOER_3", None),
    ("ANDROID_TPL_NPC_CHANGAN_YIZHANLAOBAN", None),
    ("ANDROID_TPL_NPC_JIEYINXIANNV", None),
    ("ANDROID_TPL_NPC_LAOXIA", None),
    ("ANDROID_TPL_NPC_TIANJIANG", None),
    ("ANDROID_TPL_CHAT_WOYAOQU", None),
)

STR_ROUTE_BINDINGS = (
    ("ZHUZI_TO_JINGWAI", None),
    ("JINGWAI_TO_SHITUO", None),
    ("JINGWAI_TO_MOWANG", None),
    ("CHANGAN_TO_HUANSHENG", None),
    ("CHANGAN_TO_JIANGNANYEWAI", None),
    ("CHANGAN_FLY_YIZHANLAOBAN", None),
    ("CHANGAN_FLY_JIUDIAN", None),
    ("CHANGAN_FLY_YEWAI", None),
    ("GUOJING_TO_DIFU", None),
    ("GUOJING_TO_PUTUO", None),
    ("GUOJING_TO_JINGWAI", None),
    ("JINGWAI_TO_WUZHUANG", None),
    ("JINGWAI_TO_PANSI", None),
    ("JIANYE_TO_DONGHAIWAN", None),
    ("AOLAI_TO_NVER", None),
    ("AOLAI_TO_HUAGUO", None),
    ("CHANGSHOU_TO_FANGCUN", None),
    ("CHANGSHOU_TO_CHANGSHOUJIAOWAI", None),
    ("DONGHAIWAN_TO_LONGGONG", None),
    ("CHANGSHOUJIAOWAI_TO_TIANGONG", None),
)

FLOAT_KEY_BINDINGS = (
    ("ANDROID_MATCH_THRESHOLD", KEY_ANDROID_MATCH_THRESHOLD),
    ("ANDROID_STEP_SLEEP_S", KEY_ANDROID_STEP_SLEEP_S),
    ("ANDROID_STEP_SLEEP_S_WORD_PUZZLE", KEY_ANDROID_STEP_SLEEP_S_WORD_PUZZLE),
    ("ANDROID_ARRIVAL_MAX_WAIT_S", KEY_ANDROID_ARRIVAL_MAX_WAIT_S),
    ("ANDROID_ARRIVAL_CHECK_INTERVAL_S", KEY_ANDROID_ARRIVAL_CHECK_INTERVAL_S),
)

FLOAT_THRESHOLD_BINDINGS = (
    ("ANDROID_THR_MAP_BUTTON", None),
    ("ANDROID_THR_MAP_X", None),
    ("ANDROID_THR_MAP_Y", None),
    ("ANDROID_THR_MAP_GO", None),
    ("ANDROID_THR_MENU_DAOJU", None),
    ("ANDROID_THR_PROP_FEIXINGFU", None),
    ("ANDROID_THR_PROP_USE", None),
    ("ANDROID_THR_FEIXINGFU_MAP", None),
    ("ANDROID_THR_DAOJU_CLOSE", None),
    ("ANDROID_THR_SYSTEM_TRANSFER", None),
    ("ANDROID_TRANSFER_RETRY_SLEEP_S", None),
    ("ANDROID_THR_SYSTEM_CLOSE_GUIDE", None),
    ("ANDROID_THR_SYSTEM_CLOSE_TASK", None),
    ("ANDROID_THR_SYSTEM_HIDE_DIALOG", None),
    ("ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK", None),
    ("ANDROID_THR_SYSTEM_EXPAND", None),
    ("ANDROID_THR_SYSTEM_HIDE_UI_DISABLE", None),
    ("ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE", None),
    ("ANDROID_THR_SYSTEM_BACK", None),
    ("ANDROID_THR_PROP_CHANGAN_FLAG", None),
    ("ANDROID_THR_MAP_TELEPORT_POINT", None),
    ("ANDROID_THR_BAOTU_RECEIVE_TASK", None),
    ("ANDROID_THR_NPC_XIAOER", None),
    ("ANDROID_THR_CHANGAN_HOTEL_DOOR", None),
)

INT_KEY_BINDINGS = (
    ("ANDROID_ARRIVAL_STABLE_COUNT", KEY_ANDROID_ARRIVAL_STABLE_COUNT),
    ("ANDROID_SCRCPY_MAX_FPS", KEY_ANDROID_SCRCPY_MAX_FPS),
    ("ANDROID_SCRCPY_BITRATE", KEY_ANDROID_SCRCPY_BITRATE),
    ("ANDROID_SCRCPY_MAX_WIDTH", KEY_ANDROID_SCRCPY_MAX_WIDTH),
    ("ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS", KEY_ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS),
)

INT_BINDINGS = (
    ("ANDROID_TRANSFER_RETRY", None),
    ("ANDROID_TELEPORT_TARGET_X", None),
    ("ANDROID_TELEPORT_TARGET_Y", None),
)

_bind_many(STR_KEY_BINDINGS, _bind_str)
_bind_many(STR_TEMPLATE_BINDINGS, _bind_str)
_bind_many(STR_ROUTE_BINDINGS, _bind_str)

ADB_SERIAL = env_optional_str(KEY_ADB_SERIAL)

_bind_many(FLOAT_KEY_BINDINGS, _bind_float)
_bind_many(FLOAT_THRESHOLD_BINDINGS, _bind_float)
_bind_many(INT_KEY_BINDINGS, _bind_int)
_bind_many(INT_BINDINGS, _bind_int)

SILICONFLOW_ENABLE_THINKING = env_bool(KEY_SILICONFLOW_ENABLE_THINKING, default=False)


def siliconflow_effective_timeout_s(timeout_s: float) -> float:
    s = env_optional_str(KEY_SILICONFLOW_TIMEOUT_S)
    return float(s) if s else float(timeout_s)


def _parse_xy(text: str) -> Optional[tuple]:
    s = str(text or "").strip()
    if not s:
        return None
    s = s.replace("，", ",")
    parts = [p.strip() for p in s.replace(" ", ",").split(",") if p.strip()]
    if len(parts) >= 2:
        try:
            return int(parts[0]), int(parts[1])
        except Exception:
            return None
    digits = []
    cur = ""
    for ch in s:
        if ch.isdigit():
            cur += ch
        else:
            if cur:
                digits.append(cur)
                cur = ""
    if cur:
        digits.append(cur)
    if len(digits) >= 2:
        try:
            return int(digits[0]), int(digits[1])
        except Exception:
            return None
    return None


WORD_PUZZLE_POINT_KEYS = {
    1: ("ANDROID_WORD_PUZZLE_POINT_1", "WORD_PUZZLE_POINT_1", "ANDROID_WORD_PUZZLE_P1", "WORD_PUZZLE_P1"),
    2: ("ANDROID_WORD_PUZZLE_POINT_2", "WORD_PUZZLE_POINT_2", "ANDROID_WORD_PUZZLE_P2", "WORD_PUZZLE_P2"),
    3: ("ANDROID_WORD_PUZZLE_POINT_3", "WORD_PUZZLE_POINT_3", "ANDROID_WORD_PUZZLE_P3", "WORD_PUZZLE_P3"),
    4: ("ANDROID_WORD_PUZZLE_POINT_4", "WORD_PUZZLE_POINT_4", "ANDROID_WORD_PUZZLE_P4", "WORD_PUZZLE_P4"),
}

WORD_PUZZLE_POINTS_DOC = "ANDROID_WORD_PUZZLE_POINT_1..4（格式 x,y）"


def word_puzzle_points_from_env() -> dict:
    init()
    pts = {}
    for i, keys in WORD_PUZZLE_POINT_KEYS.items():
        raw = env_str_first(keys, default="")
        xy = _parse_xy(raw)
        if xy is not None:
            pts[i] = xy
    return pts


def require_str(key: str) -> str:
    v = env_str(key, "")
    if not v:
        raise RuntimeError(f"缺少 {key}，请在环境变量或 .env 中配置")
    return v


def is_debug() -> bool:
    return env_bool(KEY_DEBUG, default=True)


def environ_copy() -> dict:
    init()
    return dict(os.environ)

