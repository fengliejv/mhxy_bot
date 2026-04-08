"""
梦幻西游押镖机器人配置文件
"""

# 游戏窗口设置
GAME_WINDOW_TITLE = "梦幻西游"

# 图像识别阈值
TEMPLATE_MATCH_THRESHOLD = 0.8
COLOR_DETECTION_SENSITIVITY = 85  # 颜色检测灵敏度百分比

# 状态监控阈值
STATUS_THRESHOLDS = {
    'hp_min_percent': 30,      # 生命值最低百分比
    'mp_min_percent': 20,      # 魔法值最低百分比
    'food_min_percent': 40,    # 饱食度最低百分比
}

# 物品管理设置
ITEM_MANAGEMENT = {
    'min_health_potions': 5,   # 最少生命药剂数量
    'min_mana_potions': 3,     # 最少魔法药剂数量
    'min_food_items': 5,       # 最少食物数量
    'inventory_full_threshold': 80,  # 背包容量警告阈值（百分比）
}

# 战斗设置
COMBAT_SETTINGS = {
    'max_battle_duration': 60,  # 最大战斗持续时间（秒）
    'escape_hp_threshold': 20,  # 逃跑生命值阈值（百分比）
    'auto_use_skills': True,    # 是否自动使用技能
    'skill_rotation': ['attack', 'skill1', 'skill2'],  # 技能轮换顺序
}

# 导航设置
NAVIGATION_SETTINGS = {
    'avoid_monsters': True,     # 是否避开路上的怪物
    'use_teleport_items': True, # 是否使用传送道具
    'movement_speed_factor': 1.0,  # 移动速度系数
}

# NPC交互设置
NPC_INTERACTION = {
    'dialog_wait_time': 2.0,    # 对话等待时间（秒）
    'interaction_retry_times': 3,  # 交互重试次数
    'click_tolerance': 10,      # 点击容差（像素）
}

# 安全设置
SAFETY_SETTINGS = {
    'enable_safety_stop': True,  # 启用安全停止机制
    'max_continuous_errors': 5,  # 最大连续错误次数
    'pause_on_error': True,      # 错误时暂停
    'error_pause_duration': 10,  # 错误暂停时长（秒）
}

# 快捷键映射
KEYBOARD_SHORTCUTS = {
    # 物品快捷键
    'health_potion': 'F1',
    'mana_potion': 'F2',
    'food_item': 'F3',
    'teleport_item': 'F4',
    
    # 功能快捷键
    'open_bag': 'B',
    'close_window': 'ESC',
    'confirm_action': 'SPACE',
    
    # 技能快捷键
    'attack': '1',
    'skill1': '2',
    'skill2': '3',
    'skill3': '4',
    'defend': '5',
    'use_item': '6',
}

# 地图坐标（示例，实际需要在游戏中测量）
MAP_COORDINATES = {
    '长安城': {'x': 375, 'y': 523},
    '建邺城': {'x': 592, 'y': 473},
    '朱紫国': {'x': 649, 'y': 373},
    '长寿村': {'x': 205, 'y': 115},
    '傲来国': {'x': 500, 'y': 100},
    '大唐国境': {'x': 400, 'y': 300},
}

# 日志设置
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'escort_bot.log',
    'max_bytes': 10485760,  # 10MB
    'backup_count': 5,
}