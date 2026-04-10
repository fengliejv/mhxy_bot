"""
梦幻西游打图自动化 - 战斗系统模块
处理战斗检测、自动战斗、技能使用等功能
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Dict, List, Optional, Tuple
from .config import (
    COMBAT_TIMEOUT,
    COMBAT_RETRY_COUNT,
    AUTO_COMBAT_SKILL,
    KEY_SHORTCUTS,
    HP_THRESHOLD_LOW,
    MP_THRESHOLD_LOW,
)
from .logger import setup_logger

logger = setup_logger("combat_system")


class CombatSystem:
    def __init__(self, window_manager, image_recognition, character_status):
        self.window_manager = window_manager
        self.image_recognition = image_recognition
        self.character_status = character_status
        
        self.in_combat = False
        self.combat_round = 0
        self.enemy_count = 0
        
        self.skill_shortcuts = {
            "attack": "1",
            "skill1": "2",
            "skill2": "3",
            "skill3": "4",
            "defend": "5",
            "auto_combat": "alt+a",
            "catch": "alt+c",
        }
        
        self.item_shortcuts = {
            "red_potion": "F1",
            "blue_potion": "F2",
        }
        
        self.combat_ui_regions = {
            "skill_bar": (100, 650, 500, 750),
            "enemy_area": (200, 100, 700, 400),
            "player_status": (50, 600, 200, 700),
        }

    def detect_combat_status(self) -> bool:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return False
        
        skill_bar_region = self.combat_ui_regions["skill_bar"]
        skill_bar = screenshot[skill_bar_region[1]:skill_bar_region[3], 
                               skill_bar_region[0]:skill_bar_region[2]]
        
        if self._detect_combat_ui(skill_bar):
            return True
        
        enemy_area = self.combat_ui_regions["enemy_area"]
        enemy_region = screenshot[enemy_area[1]:enemy_area[3],
                                  enemy_area[0]:enemy_area[2]]
        
        if self._detect_enemies(enemy_region):
            return True
        
        return False

    def _detect_combat_ui(self, skill_bar: np.ndarray) -> bool:
        if skill_bar.size == 0:
            return False
        
        hsv = cv2.cvtColor(skill_bar, cv2.COLOR_BGR2HSV)
        
        combat_ui_colors = [
            ((0, 0, 100), (180, 50, 200)),
            ((0, 50, 50), (20, 255, 255)),
            ((100, 50, 50), (130, 255, 255)),
        ]
        
        for lower, upper in combat_ui_colors:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            if np.sum(mask) > skill_bar.shape[0] * skill_bar.shape[1] * 0.1:
                return True
        
        return False

    def _detect_enemies(self, enemy_region: np.ndarray) -> bool:
        if enemy_region.size == 0:
            return False
        
        gray = cv2.cvtColor(enemy_region, cv2.COLOR_BGR2GRAY)
        
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=20,
            param1=50,
            param2=30,
            minRadius=10,
            maxRadius=50
        )
        
        if circles is not None and len(circles[0]) > 0:
            self.enemy_count = len(circles[0])
            return True
        
        return False

    def start_combat(self) -> bool:
        logger.info("开始战斗")
        
        self.in_combat = True
        self.combat_round = 0
        
        time.sleep(1.0)
        
        while self.in_combat and self.combat_round < COMBAT_TIMEOUT:
            if not self.detect_combat_status():
                logger.info("战斗已结束")
                self.in_combat = False
                break
            
            self._manage_combat_status()
            
            self._execute_combat_action()
            
            self.combat_round += 1
            time.sleep(1.5)
        
        if self.combat_round >= COMBAT_TIMEOUT:
            logger.warning("战斗超时")
            return False
        
        logger.info(f"战斗完成，共 {self.combat_round} 回合")
        return True

    def _manage_combat_status(self) -> None:
        hp_mp = self.character_status.detect_hp_mp()
        
        if hp_mp["hp"] < HP_THRESHOLD_LOW * 100:
            logger.info("血量过低，使用药品")
            self._use_health_potion()
        
        if hp_mp["mp"] < MP_THRESHOLD_LOW * 100:
            logger.info("蓝量过低，使用药品")
            self._use_mana_potion()

    def _execute_combat_action(self) -> None:
        enemies = self._find_target_enemies()
        
        if enemies:
            target = enemies[0]
            self._attack_target(target)
        else:
            self._use_auto_combat()

    def _find_target_enemies(self) -> List[Tuple[int, int]]:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return []
        
        enemy_area = self.combat_ui_regions["enemy_area"]
        enemy_region = screenshot[enemy_area[1]:enemy_area[3],
                                  enemy_area[0]:enemy_area[2]]
        
        enemies = []
        
        hsv = cv2.cvtColor(enemy_region, cv2.COLOR_BGR2HSV)
        
        enemy_colors = [
            ((0, 50, 50), (20, 255, 255)),
            ((100, 50, 50), (130, 255, 255)),
        ]
        
        for lower, upper in enemy_colors:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 300:
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"]) + enemy_area[0]
                        cy = int(M["m01"] / M["m00"]) + enemy_area[1]
                        enemies.append((cx, cy))
        
        return enemies

    def _attack_target(self, target: Tuple[int, int]) -> None:
        x, y = target
        logger.debug(f"攻击目标: ({x}, {y})")
        
        self.window_manager.click_game_coords(x, y)
        time.sleep(0.3)
        
        pyautogui.press(self.skill_shortcuts["attack"])
        time.sleep(0.5)

    def _use_auto_combat(self) -> None:
        logger.info("使用自动战斗")
        
        pyautogui.hotkey(*self.skill_shortcuts["auto_combat"].split("+"))
        time.sleep(1.0)

    def _use_health_potion(self) -> None:
        if "red_potion" in self.item_shortcuts:
            pyautogui.press(self.item_shortcuts["red_potion"])
            logger.info("使用生命药水")
            time.sleep(0.5)

    def _use_mana_potion(self) -> None:
        if "blue_potion" in self.item_shortcuts:
            pyautogui.press(self.item_shortcuts["blue_potion"])
            logger.info("使用法力药水")
            time.sleep(0.5)

    def use_skill(self, skill_name: str) -> bool:
        if skill_name in self.skill_shortcuts:
            shortcut = self.skill_shortcuts[skill_name]
            
            if "+" in shortcut:
                keys = shortcut.split("+")
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(shortcut)
            
            logger.info(f"使用技能: {skill_name}")
            time.sleep(0.5)
            return True
        
        return False

    def catch_pet(self) -> bool:
        logger.info("尝试捕捉宠物")
        
        enemies = self._find_target_enemies()
        if not enemies:
            logger.warning("没有可捕捉的目标")
            return False
        
        target = enemies[0]
        self.window_manager.click_game_coords(target[0], target[1])
        time.sleep(0.3)
        
        pyautogui.hotkey(*self.skill_shortcuts["catch"].split("+"))
        time.sleep(1.0)
        
        return True

    def flee_combat(self) -> bool:
        logger.info("尝试逃跑")
        
        pyautogui.press("esc")
        time.sleep(0.5)
        
        flee_button_pos = (self.window_manager.window_rect[2] // 2,
                          self.window_manager.window_rect[3] * 3 // 4)
        self.window_manager.click_game_coords(flee_button_pos[0], flee_button_pos[1])
        time.sleep(1.0)
        
        if not self.detect_combat_status():
            logger.info("逃跑成功")
            self.in_combat = False
            return True
        
        logger.warning("逃跑失败")
        return False

    def wait_for_combat_end(self, timeout: int = 60) -> bool:
        logger.info("等待战斗结束")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.detect_combat_status():
                logger.info("战斗已结束")
                self.in_combat = False
                return True
            
            time.sleep(1.0)
        
        logger.warning("等待战斗结束超时")
        return False

    def get_combat_info(self) -> Dict:
        return {
            "in_combat": self.in_combat,
            "combat_round": self.combat_round,
            "enemy_count": self.enemy_count,
        }
