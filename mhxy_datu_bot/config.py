"""
梦幻西游打图自动化 - 配置文件
"""

# 游戏窗口配置
GAME_WINDOW_TITLE = "梦幻西游"
GAME_WINDOW_CLASS = "MHXYMainFrame"
GAME_WINDOW_DEFAULT_WIDTH = 1024
GAME_WINDOW_DEFAULT_HEIGHT = 768

# 游戏路径配置
GAME_CLIENT_PATH = r"C:\Program Files\梦幻西游\my.exe"

# 长安酒店配置
HOTEL_ENTRANCE_COORDS = (460, 164)
SHOP_WAITER_NAME = "店小二"
SHOP_WAITER_DIALOG_OPTION = "听听无妨"
TASK_COST_SILVER = 500

# 角色状态配置
HP_THRESHOLD_LOW = 0.3
HP_THRESHOLD_MEDIUM = 0.6
MP_THRESHOLD_LOW = 0.3
MP_THRESHOLD_MEDIUM = 0.6

# 背包配置
INVENTORY_MAX_SLOTS = 20
BAG_MAX_SLOTS = 20
ESSENTIAL_ITEMS = {
    "飞行符": {"min_count": 20, "location": "仙缘阁"},
    "包子": {"min_count": 50, "location": "酒店伙计"},
    "导标旗": {"min_count": 1, "location": "自行插旗"},
}

# 三界功绩配置
SANJIE_MIN_THRESHOLD = 50
SANJIE_WARNING_THRESHOLD = 100

# 银两配置
SILVER_MIN_REQUIRED = 100000

# 打图任务配置
MAX_DAILY_TASKS = 350
SANJIE_FREE_TASKS = 40
SANJIE_COST_PER_TASK = 1

# 强盗可能出现地图
BANDIT_MAPS = {
    "大唐国境": {"teleport": "驿站", "coords": [(200, 100), (300, 150)]},
    "江南野外": {"teleport": "飞行符", "coords": [(150, 80), (250, 120)]},
    "东海湾": {"teleport": "傲来驿站", "coords": [(100, 50), (200, 100)]},
    "傲来国": {"teleport": "长安驿站", "coords": [(130, 60), (180, 90)]},
    "女儿村": {"teleport": "傲来导标旗", "coords": [(120, 70), (170, 110)]},
    "建邺城": {"teleport": "飞行符", "coords": [(110, 60), (160, 100)]},
    "普陀山": {"teleport": "大唐国境传送", "coords": [(90, 40), (140, 80)]},
    "大唐境外": {"teleport": "飞行符", "coords": [(100, 50), (150, 90)]},
    "狮驼岭": {"teleport": "飞行符", "coords": [(110, 60), (160, 100)]},
    "五庄观": {"teleport": "飞行符", "coords": [(120, 70), (170, 110)]},
}

# 战斗配置
COMBAT_TIMEOUT = 60
COMBAT_RETRY_COUNT = 3
AUTO_COMBAT_SKILL = "横扫千军"

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "mhxy_datu.log"

# 快捷键配置
KEY_SHORTCUTS = {
    "inventory": "Alt+E",
    "character": "Alt+W",
    "task": "Alt+Q",
    "skill": "Alt+S",
    "auto_combat": "Alt+A",
}

# 颜色检测配置 (用于状态检测)
COLOR_RANGES = {
    "hp_bar": {"r": (200, 255), "g": (0, 50), "b": (0, 50)},
    "mp_bar": {"r": (0, 50), "g": (0, 50), "b": (200, 255)},
}
