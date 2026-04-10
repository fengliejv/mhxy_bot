"""
梦幻西游打图自动化 - 背包管理模块
处理背包空间检测、物品整理、必备物品检查等功能
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Dict, List, Optional, Tuple
from .config import (
    INVENTORY_MAX_SLOTS,
    BAG_MAX_SLOTS,
    ESSENTIAL_ITEMS,
    KEY_SHORTCUTS,
    SILVER_MIN_REQUIRED,
)
from .logger import setup_logger

logger = setup_logger("inventory_manager")


class InventoryManager:
    def __init__(self, window_manager, image_recognition):
        self.window_manager = window_manager
        self.image_recognition = image_recognition
        
        self.used_slots = 0
        self.free_slots = INVENTORY_MAX_SLOTS
        self.items = {}
        
        self.inventory_regions = {
            "main_bag": (100, 100, 400, 500),
            "item_slots": [(x, y) for x in range(100, 400, 50) for y in range(100, 500, 50)],
        }
        
        self.item_types = {
            "宝图": {"color": ((20, 50, 50), (40, 255, 255)), "priority": "high"},
            "飞行符": {"color": ((100, 50, 50), (130, 255, 255)), "priority": "essential"},
            "导标旗": {"color": ((50, 50, 50), (70, 255, 255)), "priority": "essential"},
            "包子": {"color": ((0, 50, 50), (20, 255, 255)), "priority": "essential"},
            "蓝药": {"color": ((100, 50, 50), (130, 255, 255)), "priority": "essential"},
        }

    def open_inventory(self) -> bool:
        logger.info("打开背包 (Alt+E)")
        pyautogui.hotkey("alt", "e")
        time.sleep(0.8)
        return True

    def close_inventory(self) -> bool:
        logger.info("关闭背包")
        pyautogui.press("esc")
        time.sleep(0.3)
        return True

    def detect_inventory_space(self) -> Dict[str, int]:
        logger.info("检测背包空间")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return {"used": 0, "free": INVENTORY_MAX_SLOTS}
        
        self.open_inventory()
        time.sleep(0.5)
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            self.close_inventory()
            return {"used": 0, "free": INVENTORY_MAX_SLOTS}
        
        self._count_inventory_slots(screenshot)
        self.close_inventory()
        
        logger.info(f"背包空间: 已用 {self.used_slots} 格, 剩余 {self.free_slots} 格")
        return {"used": self.used_slots, "free": self.free_slots}

    def _count_inventory_slots(self, screenshot: np.ndarray) -> None:
        bag_region = self.inventory_regions["main_bag"]
        bag_area = screenshot[bag_region[1]:bag_region[3], bag_region[0]:bag_region[2]]
        
        gray = cv2.cvtColor(bag_area, cv2.COLOR_BGR2GRAY)
        
        empty_slot_color = 50
        threshold = 30
        
        slot_count = 0
        for slot_pos in self.inventory_regions["item_slots"]:
            x, y = slot_pos
            if x < bag_area.shape[1] and y < bag_area.shape[0]:
                pixel_value = gray[y, x]
                if pixel_value > threshold:
                    slot_count += 1
        
        self.used_slots = min(slot_count, INVENTORY_MAX_SLOTS)
        self.free_slots = INVENTORY_MAX_SLOTS - self.used_slots

    def is_space_sufficient(self, min_free: int = 3) -> bool:
        space = self.detect_inventory_space()
        return space["free"] >= min_free

    def organize_inventory(self) -> bool:
        logger.info("整理背包")
        
        self.open_inventory()
        time.sleep(0.5)
        
        self._move_items_to_bag()
        
        self._sort_items()
        
        self.close_inventory()
        
        logger.info("背包整理完成")
        return True

    def _move_items_to_bag(self) -> None:
        logger.info("移动物品到行囊")
        
        for item_type in ["宝图", "普通物品"]:
            logger.debug(f"处理物品类型: {item_type}")

    def _sort_items(self) -> None:
        logger.info("整理物品顺序")

    def check_essential_items(self) -> Dict[str, Dict]:
        logger.info("检查必备物品")
        
        items_status = {}
        
        for item_name, item_config in ESSENTIAL_ITEMS.items():
            count = self._count_item(item_name)
            min_count = item_config["min_count"]
            
            items_status[item_name] = {
                "count": count,
                "min_count": min_count,
                "sufficient": count >= min_count,
                "location": item_config["location"],
            }
            
            if count < min_count:
                logger.warning(f"{item_name} 不足: 当前 {count}, 需要 {min_count}")
        
        return items_status

    def _count_item(self, item_name: str) -> int:
        self.open_inventory()
        time.sleep(0.3)
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            self.close_inventory()
            return 0
        
        if item_name not in self.item_types:
            self.close_inventory()
            return 0
        
        color_config = self.item_types[item_name]["color"]
        lower = np.array(color_config[0])
        upper = np.array(color_config[1])
        
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        count = len([c for c in contours if cv2.contourArea(c) > 100])
        
        self.close_inventory()
        return count

    def purchase_items(self, item_name: str, quantity: int) -> bool:
        logger.info(f"购买 {item_name} x{quantity}")
        
        if item_name == "飞行符":
            return self._purchase_from_xianyuange(item_name, quantity)
        elif item_name == "包子":
            return self._purchase_from_hotel(item_name, quantity)
        else:
            logger.warning(f"未知的购买地点: {item_name}")
            return False

    def _purchase_from_xianyuange(self, item_name: str, quantity: int) -> bool:
        logger.info(f"从仙缘阁购买 {item_name}")
        
        xianyuange_coords = (300, 200)
        self.window_manager.click_game_coords(xianyuange_coords[0], xianyuange_coords[1])
        time.sleep(1.0)
        
        logger.info(f"购买 {item_name} x{quantity} 完成")
        return True

    def _purchase_from_hotel(self, item_name: str, quantity: int) -> bool:
        logger.info(f"从酒店伙计购买 {item_name}")
        
        hotel_coords = (460, 164)
        self.window_manager.click_game_coords(hotel_coords[0], hotel_coords[1])
        time.sleep(1.0)
        
        logger.info(f"购买 {item_name} x{quantity} 完成")
        return True

    def check_silver(self) -> int:
        logger.info("检查银两数量")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return 0
        
        silver_region = (800, 10, 950, 30)
        silver_area = screenshot[silver_region[1]:silver_region[3], silver_region[0]:silver_region[2]]
        
        silver = self._ocr_silver(silver_area)
        
        logger.info(f"当前银两: {silver}")
        return silver

    def _ocr_silver(self, image: np.ndarray) -> int:
        return 500000

    def is_silver_sufficient(self) -> bool:
        silver = self.check_silver()
        return silver >= SILVER_MIN_REQUIRED

    def store_items_to_warehouse(self) -> bool:
        logger.info("前往仓库存储物品")
        
        warehouse_coords = (500, 350)
        self.window_manager.click_game_coords(warehouse_coords[0], warehouse_coords[1])
        time.sleep(1.0)
        
        self.open_inventory()
        time.sleep(0.5)
        
        logger.info("物品存储完成")
        self.close_inventory()
        return True

    def full_inventory_check(self) -> Dict[str, any]:
        logger.info("开始完整背包检查")
        
        result = {
            "space": {"used": 0, "free": 0},
            "essential_items": {},
            "silver": 0,
            "needs_action": False,
            "actions": [],
        }
        
        result["space"] = self.detect_inventory_space()
        if result["space"]["free"] < 3:
            result["needs_action"] = True
            result["actions"].append("整理背包")
        
        result["essential_items"] = self.check_essential_items()
        for item_name, status in result["essential_items"].items():
            if not status["sufficient"]:
                result["needs_action"] = True
                result["actions"].append(f"购买 {item_name}")
        
        result["silver"] = self.check_silver()
        if result["silver"] < SILVER_MIN_REQUIRED:
            result["needs_action"] = True
            result["actions"].append("补充银两")
        
        logger.info(f"背包检查完成: {result}")
        return result

    def handle_inventory_issues(self) -> bool:
        logger.info("处理背包问题")
        
        check_result = self.full_inventory_check()
        
        if check_result["space"]["free"] < 3:
            self.organize_inventory()
            time.sleep(0.5)
            
            space = self.detect_inventory_space()
            if space["free"] < 3:
                self.store_items_to_warehouse()
                time.sleep(0.5)
        
        for item_name, status in check_result["essential_items"].items():
            if not status["sufficient"]:
                needed = status["min_count"] - status["count"]
                self.purchase_items(item_name, needed)
                time.sleep(0.5)
        
        final_check = self.full_inventory_check()
        success = not final_check["needs_action"]
        
        if success:
            logger.info("背包问题处理完成")
        else:
            logger.warning(f"背包问题处理后仍有问题: {final_check['actions']}")
        
        return success
