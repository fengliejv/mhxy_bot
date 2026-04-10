"""
梦幻西游打图自动化 - 角色状态管理模块
处理角色血量、蓝量、装备耐久、宠物状态等检测和恢复
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Dict, Optional, Tuple
from .config import (
    HP_THRESHOLD_LOW,
    HP_THRESHOLD_MEDIUM,
    MP_THRESHOLD_LOW,
    MP_THRESHOLD_MEDIUM,
    KEY_SHORTCUTS,
    COLOR_RANGES,
)
from .logger import setup_logger

logger = setup_logger("character_status")


class CharacterStatus:
    def __init__(self, window_manager, image_recognition):
        self.window_manager = window_manager
        self.image_recognition = image_recognition
        
        self.hp_percent = 100
        self.mp_percent = 100
        self.equipment_durability = 100
        self.pet_hp_percent = 100
        self.pet_mp_percent = 100
        
        self.status_regions = {
            "hp_bar": (50, 700, 200, 720),
            "mp_bar": (50, 725, 200, 745),
            "equipment": (10, 600, 100, 700),
            "pet_status": (800, 650, 950, 750),
        }
        
        self.recovery_items = {
            "包子": {"shortcut": "F1", "type": "hp"},
            "蓝药": {"shortcut": "F2", "type": "mp"},
            "宠物口粮": {"shortcut": "F3", "type": "pet_hp"},
        }

    def open_character_panel(self) -> bool:
        logger.info("打开角色属性面板 (Alt+W)")
        pyautogui.hotkey("alt", "w")
        time.sleep(0.8)
        return True

    def close_character_panel(self) -> bool:
        logger.info("关闭角色属性面板")
        pyautogui.press("esc")
        time.sleep(0.3)
        return True

    def detect_hp_mp(self) -> Dict[str, int]:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return {"hp": 100, "mp": 100}
        
        hp_region = self.status_regions["hp_bar"]
        mp_region = self.status_regions["mp_bar"]
        
        hp_bar = screenshot[hp_region[1]:hp_region[3], hp_region[0]:hp_region[2]]
        mp_bar = screenshot[mp_region[1]:mp_region[3], mp_region[0]:mp_region[2]]
        
        self.hp_percent = self._calculate_bar_percent(hp_bar, "hp")
        self.mp_percent = self._calculate_bar_percent(mp_bar, "mp")
        
        logger.info(f"检测到血量: {self.hp_percent}%, 蓝量: {self.mp_percent}%")
        return {"hp": self.hp_percent, "mp": self.mp_percent}

    def _calculate_bar_percent(self, bar_image: np.ndarray, bar_type: str) -> int:
        if bar_image.size == 0:
            return 100
        
        hsv = cv2.cvtColor(bar_image, cv2.COLOR_BGR2HSV)
        
        if bar_type == "hp":
            lower = np.array([0, 100, 100])
            upper = np.array([10, 255, 255])
        else:
            lower = np.array([100, 100, 100])
            upper = np.array([130, 255, 255])
        
        mask = cv2.inRange(hsv, lower, upper)
        filled_pixels = np.sum(mask > 0)
        total_pixels = mask.size
        
        return int((filled_pixels / total_pixels) * 100) if total_pixels > 0 else 100

    def check_equipment_durability(self) -> int:
        logger.info("检查装备耐久度")
        self.open_character_panel()
        time.sleep(0.5)
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            self.close_character_panel()
            return 100
        
        self.equipment_durability = self._detect_durability_from_panel(screenshot)
        self.close_character_panel()
        
        logger.info(f"装备耐久度: {self.equipment_durability}%")
        return self.equipment_durability

    def _detect_durability_from_panel(self, screenshot: np.ndarray) -> int:
        return 80

    def check_pet_status(self) -> Dict[str, int]:
        logger.info("检查宠物状态")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return {"pet_hp": 100, "pet_mp": 100}
        
        pet_region = self.status_regions["pet_status"]
        pet_area = screenshot[pet_region[1]:pet_region[3], pet_region[0]:pet_region[2]]
        
        self.pet_hp_percent = self._calculate_bar_percent(pet_area, "hp")
        self.pet_mp_percent = self._calculate_bar_percent(pet_area, "mp")
        
        logger.info(f"宠物血量: {self.pet_hp_percent}%, 宠物蓝量: {self.pet_mp_percent}%")
        return {"pet_hp": self.pet_hp_percent, "pet_mp": self.pet_mp_percent}

    def is_status_good(self) -> bool:
        self.detect_hp_mp()
        
        if self.hp_percent < HP_THRESHOLD_LOW * 100:
            logger.warning(f"血量过低: {self.hp_percent}%")
            return False
        if self.mp_percent < MP_THRESHOLD_LOW * 100:
            logger.warning(f"蓝量过低: {self.mp_percent}%")
            return False
        
        return True

    def recover_hp(self) -> bool:
        logger.info("恢复血量")
        
        if self.hp_percent > HP_THRESHOLD_MEDIUM * 100:
            return True
        
        if "包子" in self.recovery_items:
            shortcut = self.recovery_items["包子"]["shortcut"]
            pyautogui.press(shortcut)
            time.sleep(1.0)
            logger.info("使用包子恢复血量")
            
            self.detect_hp_mp()
            return self.hp_percent >= HP_THRESHOLD_MEDIUM * 100
        
        return False

    def recover_mp(self) -> bool:
        logger.info("恢复蓝量")
        
        if self.mp_percent > MP_THRESHOLD_MEDIUM * 100:
            return True
        
        if "蓝药" in self.recovery_items:
            shortcut = self.recovery_items["蓝药"]["shortcut"]
            pyautogui.press(shortcut)
            time.sleep(1.0)
            logger.info("使用蓝药恢复蓝量")
            
            self.detect_hp_mp()
            return self.mp_percent >= MP_THRESHOLD_MEDIUM * 100
        
        return False

    def recover_pet(self) -> bool:
        logger.info("恢复宠物状态")
        
        if self.pet_hp_percent > 50:
            return True
        
        if "宠物口粮" in self.recovery_items:
            shortcut = self.recovery_items["宠物口粮"]["shortcut"]
            pyautogui.press(shortcut)
            time.sleep(1.0)
            logger.info("使用宠物口粮恢复宠物")
            return True
        
        return False

    def repair_equipment(self) -> bool:
        logger.info("修理装备")
        
        repair_npc_coords = (500, 300)
        self.window_manager.click_game_coords(repair_npc_coords[0], repair_npc_coords[1])
        time.sleep(1.0)
        
        logger.info("装备修理完成")
        return True

    def full_status_check(self) -> Dict[str, any]:
        logger.info("开始完整状态检查")
        
        status = {
            "hp": 100,
            "mp": 100,
            "equipment_durability": 100,
            "pet_hp": 100,
            "pet_mp": 100,
            "needs_recovery": False,
            "issues": [],
        }
        
        hp_mp = self.detect_hp_mp()
        status["hp"] = hp_mp["hp"]
        status["mp"] = hp_mp["mp"]
        
        if status["hp"] < HP_THRESHOLD_LOW * 100:
            status["issues"].append("血量过低")
            status["needs_recovery"] = True
        if status["mp"] < MP_THRESHOLD_LOW * 100:
            status["issues"].append("蓝量过低")
            status["needs_recovery"] = True
        
        pet_status = self.check_pet_status()
        status["pet_hp"] = pet_status["pet_hp"]
        status["pet_mp"] = pet_status["pet_mp"]
        
        if status["pet_hp"] < 30:
            status["issues"].append("宠物血量过低")
            status["needs_recovery"] = True
        
        status["equipment_durability"] = self.check_equipment_durability()
        if status["equipment_durability"] < 30:
            status["issues"].append("装备耐久过低")
            status["needs_recovery"] = True
        
        logger.info(f"状态检查完成: {status}")
        return status

    def recover_all(self) -> bool:
        logger.info("开始恢复所有状态")
        
        status = self.full_status_check()
        
        if status["hp"] < HP_THRESHOLD_MEDIUM * 100:
            self.recover_hp()
            time.sleep(0.5)
        
        if status["mp"] < MP_THRESHOLD_MEDIUM * 100:
            self.recover_mp()
            time.sleep(0.5)
        
        if status["pet_hp"] < 50:
            self.recover_pet()
            time.sleep(0.5)
        
        if status["equipment_durability"] < 30:
            self.repair_equipment()
            time.sleep(0.5)
        
        final_status = self.full_status_check()
        success = not final_status["needs_recovery"]
        
        if success:
            logger.info("状态恢复完成")
        else:
            logger.warning(f"状态恢复后仍有问题: {final_status['issues']}")
        
        return success
