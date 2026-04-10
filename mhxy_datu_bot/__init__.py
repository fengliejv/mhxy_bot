"""
梦幻西游打图自动化
自动完成打图任务的机器人
"""

from .main import DatuBot, main
from .config import *
from .window_manager import WindowManager
from .image_recognition import ImageRecognition
from .character_status import CharacterStatus
from .inventory_manager import InventoryManager
from .navigation_system import NavigationSystem
from .combat_system import CombatSystem
from .npc_interaction import NPCInteraction
from .datu_task import DatuTask

__version__ = "1.0.0"
__author__ = "MHXY Datu Bot"
__all__ = [
    "DatuBot",
    "main",
    "WindowManager",
    "ImageRecognition",
    "CharacterStatus",
    "InventoryManager",
    "NavigationSystem",
    "CombatSystem",
    "NPCInteraction",
    "DatuTask",
]
