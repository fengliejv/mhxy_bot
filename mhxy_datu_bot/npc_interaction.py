"""
梦幻西游打图自动化 - NPC交互模块
处理与游戏内NPC的交互，包括店小二、商人等
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Dict, List, Optional, Tuple
from .config import SHOP_WAITER_NAME, SHOP_WAITER_DIALOG_OPTION
from .logger import setup_logger

logger = setup_logger("npc_interaction")


class NPCInteraction:
    def __init__(self, window_manager, image_recognition):
        self.window_manager = window_manager
        self.image_recognition = image_recognition
        
        self.npc_templates = {}
        
        self.npc_colors = {
            "店小二": [((0, 50, 50), (20, 255, 255)), ((100, 50, 50), (130, 255, 255))],
            "酒店伙计": [((20, 50, 50), (40, 255, 255)), ((50, 50, 50), (70, 255, 255))],
            "仓库管理员": [((100, 50, 50), (130, 255, 255))],
            "驿站传送员": [((0, 0, 100), (180, 50, 200))],
        }
        
        self.npc_known_positions = {
            "店小二": [(460, 164), (450, 170), (470, 160)],
            "酒店伙计": [(480, 180), (470, 175)],
            "仓库管理员": [(500, 350), (510, 340)],
            "驿站传送员": [(500, 300), (490, 310)],
        }
        
        self.dialog_regions = {
            "main_dialog": (200, 300, 600, 500),
            "options": (200, 450, 600, 550),
        }

    def find_npc(self, npc_name: str) -> Optional[Tuple[int, int]]:
        logger.info(f"寻找NPC: {npc_name}")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        if npc_name in self.npc_colors:
            for color_range in self.npc_colors[npc_name]:
                lower, upper = color_range
                pos = self._detect_npc_by_color(screenshot, lower, upper)
                if pos:
                    logger.info(f"通过颜色检测找到 {npc_name}: {pos}")
                    return pos
        
        if npc_name in self.npc_known_positions:
            for known_pos in self.npc_known_positions[npc_name]:
                if self._verify_npc_at_position(screenshot, known_pos, npc_name):
                    logger.info(f"在已知位置找到 {npc_name}: {known_pos}")
                    return known_pos
        
        pos = self._scan_for_npc(screenshot, npc_name)
        if pos:
            logger.info(f"扫描找到 {npc_name}: {pos}")
            return pos
        
        logger.warning(f"未找到NPC: {npc_name}")
        return None

    def _detect_npc_by_color(self, screenshot: np.ndarray, 
                              lower: Tuple[int, int, int], 
                              upper: Tuple[int, int, int]) -> Optional[Tuple[int, int]]:
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return (cx, cy)
        
        return None

    def _verify_npc_at_position(self, screenshot: np.ndarray, 
                                 position: Tuple[int, int], 
                                 npc_name: str) -> bool:
        x, y = position
        roi_size = 50
        
        x1 = max(0, x - roi_size)
        y1 = max(0, y - roi_size)
        x2 = min(screenshot.shape[1], x + roi_size)
        y2 = min(screenshot.shape[0], y + roi_size)
        
        roi = screenshot[y1:y2, x1:x2]
        
        if roi.size == 0:
            return False
        
        color_variance = np.var(roi.reshape(-1, roi.shape[-1]), axis=0).mean()
        
        return color_variance > 500

    def _scan_for_npc(self, screenshot: np.ndarray, npc_name: str) -> Optional[Tuple[int, int]]:
        height, width = screenshot.shape[:2]
        
        scan_points = [
            (width // 3, height // 3),
            (2 * width // 3, height // 3),
            (width // 2, height // 2),
            (width // 3, 2 * height // 3),
            (2 * width // 3, 2 * height // 3),
        ]
        
        for x, y in scan_points:
            if self._verify_npc_at_position(screenshot, (x, y), npc_name):
                return (x, y)
        
        return None

    def click_npc(self, npc_pos: Tuple[int, int]) -> bool:
        x, y = npc_pos
        logger.info(f"点击NPC: ({x}, {y})")
        
        self.window_manager.click_game_coords(x, y)
        time.sleep(1.0)
        
        return True

    def interact_with_npc(self, npc_name: str) -> bool:
        logger.info(f"与NPC交互: {npc_name}")
        
        npc_pos = self.find_npc(npc_name)
        if npc_pos is None:
            logger.warning(f"无法找到NPC: {npc_name}")
            return False
        
        self.click_npc(npc_pos)
        time.sleep(1.0)
        
        return True

    def select_dialog_option(self, option_text: str = None, option_index: int = 0) -> bool:
        logger.info(f"选择对话选项: {option_text or f'第{option_index+1}个'}")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return False
        
        options_region = self.dialog_regions["options"]
        options_area = screenshot[options_region[1]:options_region[3],
                                  options_region[0]:options_region[2]]
        
        if option_text:
            text = self.image_recognition.detect_text_region(options_area)
            if text and option_text in text:
                click_pos = (options_region[0] + 200, options_region[1] + 50)
                self.window_manager.click_game_coords(click_pos[0], click_pos[1])
                time.sleep(0.5)
                return True
        else:
            option_height = (options_region[3] - options_region[1]) // 4
            click_y = options_region[1] + option_height * (option_index + 0.5)
            click_x = (options_region[0] + options_region[2]) // 2
            
            self.window_manager.click_game_coords(click_x, int(click_y))
            time.sleep(0.5)
            return True
        
        return False

    def close_dialog(self) -> bool:
        logger.info("关闭对话框")
        
        pyautogui.press("esc")
        time.sleep(0.3)
        
        return True

    def wait_for_dialog(self, timeout: float = 5.0) -> bool:
        logger.info("等待对话框出现")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            screenshot = self.window_manager.capture_screen()
            if screenshot is None:
                time.sleep(0.5)
                continue
            
            dialog_region = self.dialog_regions["main_dialog"]
            dialog_area = screenshot[dialog_region[1]:dialog_region[3],
                                     dialog_region[0]:dialog_region[2]]
            
            if self._is_dialog_visible(dialog_area):
                logger.info("对话框已出现")
                return True
            
            time.sleep(0.5)
        
        logger.warning("等待对话框超时")
        return False

    def _is_dialog_visible(self, dialog_area: np.ndarray) -> bool:
        if dialog_area.size == 0:
            return False
        
        gray = cv2.cvtColor(dialog_area, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        return edge_density > 0.05

    def talk_to_waiter(self) -> bool:
        logger.info("与店小二对话")
        
        if not self.interact_with_npc(SHOP_WAITER_NAME):
            return False
        
        if not self.wait_for_dialog():
            return False
        
        return True

    def buy_from_npc(self, npc_name: str, item_name: str, quantity: int) -> bool:
        logger.info(f"从 {npc_name} 购买 {item_name} x{quantity}")
        
        if not self.interact_with_npc(npc_name):
            return False
        
        if not self.wait_for_dialog():
            return False
        
        if not self.select_dialog_option("购买"):
            self.select_dialog_option(option_index=0)
        
        time.sleep(1.0)
        
        self._select_item_to_buy(item_name)
        
        self._set_quantity(quantity)
        
        self._confirm_purchase()
        
        self.close_dialog()
        
        logger.info(f"购买完成: {item_name} x{quantity}")
        return True

    def _select_item_to_buy(self, item_name: str) -> bool:
        logger.debug(f"选择物品: {item_name}")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return False
        
        shop_region = (150, 150, 450, 500)
        shop_area = screenshot[shop_region[1]:shop_region[3],
                               shop_region[0]:shop_region[2]]
        
        text = self.image_recognition.detect_text_region(shop_area)
        
        if text and item_name in text:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if item_name in line:
                    click_y = shop_region[1] + 30 + i * 25
                    click_x = shop_region[0] + 50
                    self.window_manager.click_game_coords(click_x, click_y)
                    return True
        
        default_pos = (shop_region[0] + 50, shop_region[1] + 50)
        self.window_manager.click_game_coords(default_pos[0], default_pos[1])
        return True

    def _set_quantity(self, quantity: int) -> bool:
        logger.debug(f"设置数量: {quantity}")
        
        quantity_input_pos = (500, 400)
        self.window_manager.click_game_coords(quantity_input_pos[0], quantity_input_pos[1])
        time.sleep(0.3)
        
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        
        pyautogui.typewrite(str(quantity))
        time.sleep(0.3)
        
        return True

    def _confirm_purchase(self) -> bool:
        logger.debug("确认购买")
        
        confirm_pos = (400, 450)
        self.window_manager.click_game_coords(confirm_pos[0], confirm_pos[1])
        time.sleep(0.5)
        
        return True

    def sell_to_npc(self, npc_name: str, item_name: str) -> bool:
        logger.info(f"向 {npc_name} 出售 {item_name}")
        
        if not self.interact_with_npc(npc_name):
            return False
        
        if not self.wait_for_dialog():
            return False
        
        if not self.select_dialog_option("出售"):
            self.select_dialog_option(option_index=1)
        
        time.sleep(1.0)
        
        self.close_dialog()
        
        return True

    def store_items(self, npc_name: str = "仓库管理员") -> bool:
        logger.info(f"在 {npc_name} 存储物品")
        
        if not self.interact_with_npc(npc_name):
            return False
        
        if not self.wait_for_dialog():
            return False
        
        if not self.select_dialog_option("存入"):
            self.select_dialog_option(option_index=0)
        
        time.sleep(1.0)
        
        self.close_dialog()
        
        return True
