"""
梦幻西游打图自动化 - 导航系统模块
处理地图传送、坐标移动、路径规划等功能
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Dict, List, Optional, Tuple
from .config import BANDIT_MAPS, KEY_SHORTCUTS
from .logger import setup_logger

logger = setup_logger("navigation_system")


class NavigationSystem:
    def __init__(self, window_manager, image_recognition):
        self.window_manager = window_manager
        self.image_recognition = image_recognition
        
        self.current_map = None
        self.current_coords = (0, 0)
        
        self.teleport_items = {
            "飞行符": {"shortcut": "F5", "maps": ["长安城", "建邺城", "傲来国", "长寿村"]},
            "导标旗": {"shortcut": "F6", "maps": ["长安城", "大唐国境", "江南野外"]},
        }
        
        self.map_connections = {
            "长安城": {"大唐国境": (375, 550), "江南野外": (200, 300)},
            "大唐国境": {"长安城": (375, 490), "建邺城": (592, 450)},
            "建邺城": {"大唐国境": (592, 500), "东海湾": (100, 200)},
            "傲来国": {"女儿村": (130, 60), "东海湾": (500, 100)},
            "长寿村": {"大唐境外": (205, 115)},
            "江南野外": {"长安城": (150, 80), "建邺城": (250, 120)},
            "东海湾": {"建邺城": (100, 50), "傲来国": (200, 100)},
            "女儿村": {"傲来国": (120, 70)},
            "大唐境外": {"长寿村": (100, 50), "狮驼岭": (150, 90)},
            "狮驼岭": {"大唐境外": (110, 60)},
            "普陀山": {"大唐国境": (90, 40)},
            "五庄观": {"大唐境外": (120, 70)},
        }
        
        self.teleport_npcs = {
            "驿站传送员": {"location": "长安城", "coords": (500, 300)},
        }

    def detect_current_map(self) -> Optional[str]:
        logger.info("检测当前地图")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        map_name_region = (10, 10, 150, 40)
        map_name_area = screenshot[map_name_region[1]:map_name_region[3],
                                   map_name_region[0]:map_name_region[2]]
        
        text = self.image_recognition.detect_text_region(map_name_area)
        
        if text:
            for map_name in self.map_connections.keys():
                if map_name in text:
                    self.current_map = map_name
                    logger.info(f"当前地图: {map_name}")
                    return map_name
        
        self.current_map = "长安城"
        return self.current_map

    def teleport_to(self, target_map: str) -> bool:
        logger.info(f"传送到: {target_map}")
        
        current = self.detect_current_map()
        if current == target_map:
            logger.info("已在目标地图")
            return True
        
        if self._use_fly_symbol(target_map):
            return True
        
        if self._use_guide_flag(target_map):
            return True
        
        if self._use_station_transport(target_map):
            return True
        
        logger.warning(f"无法传送到 {target_map}，尝试步行")
        return self.walk_to_map(target_map)

    def _use_fly_symbol(self, target_map: str) -> bool:
        if target_map not in self.teleport_items["飞行符"]["maps"]:
            return False
        
        logger.info(f"使用飞行符前往 {target_map}")
        
        pyautogui.press(self.teleport_items["飞行符"]["shortcut"])
        time.sleep(1.0)
        
        target_coords = self._get_fly_symbol_target_coords(target_map)
        if target_coords:
            self.window_manager.click_game_coords(target_coords[0], target_coords[1])
            time.sleep(3.0)
            
            new_map = self.detect_current_map()
            if new_map == target_map:
                logger.info(f"成功传送到 {target_map}")
                return True
        
        return False

    def _get_fly_symbol_target_coords(self, map_name: str) -> Optional[Tuple[int, int]]:
        fly_symbol_coords = {
            "长安城": (200, 150),
            "建邺城": (300, 150),
            "傲来国": (400, 150),
            "长寿村": (500, 150),
        }
        return fly_symbol_coords.get(map_name)

    def _use_guide_flag(self, target_map: str) -> bool:
        if target_map not in self.teleport_items["导标旗"]["maps"]:
            return False
        
        logger.info(f"使用导标旗前往 {target_map}")
        
        pyautogui.press(self.teleport_items["导标旗"]["shortcut"])
        time.sleep(1.0)
        
        target_coords = self._get_guide_flag_target_coords(target_map)
        if target_coords:
            self.window_manager.click_game_coords(target_coords[0], target_coords[1])
            time.sleep(3.0)
            
            new_map = self.detect_current_map()
            if new_map == target_map:
                logger.info(f"成功传送到 {target_map}")
                return True
        
        return False

    def _get_guide_flag_target_coords(self, map_name: str) -> Optional[Tuple[int, int]]:
        guide_flag_coords = {
            "长安城": (150, 200),
            "大唐国境": (250, 200),
            "江南野外": (350, 200),
        }
        return guide_flag_coords.get(map_name)

    def _use_station_transport(self, target_map: str) -> bool:
        logger.info(f"尝试通过驿站传送到 {target_map}")
        
        station_coords = (500, 300)
        self.window_manager.click_game_coords(station_coords[0], station_coords[1])
        time.sleep(1.0)
        
        transport_option = self._find_transport_option(target_map)
        if transport_option:
            self.window_manager.click_game_coords(transport_option[0], transport_option[1])
            time.sleep(3.0)
            
            new_map = self.detect_current_map()
            if new_map == target_map:
                logger.info(f"成功传送到 {target_map}")
                return True
        
        return False

    def _find_transport_option(self, target_map: str) -> Optional[Tuple[int, int]]:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        dialog_region = (200, 200, 600, 500)
        dialog_area = screenshot[dialog_region[1]:dialog_region[3],
                                 dialog_region[0]:dialog_region[2]]
        
        text = self.image_recognition.detect_text_region(dialog_area)
        
        if text and target_map in text:
            return (dialog_region[0] + 200, dialog_region[1] + 150)
        
        return None

    def walk_to_map(self, target_map: str) -> bool:
        logger.info(f"步行前往: {target_map}")
        
        current = self.detect_current_map()
        if current == target_map:
            return True
        
        path = self._calculate_path(current, target_map)
        if not path:
            logger.error(f"无法找到从 {current} 到 {target_map} 的路径")
            return False
        
        logger.info(f"路径: {' -> '.join(path)}")
        
        for i in range(len(path) - 1):
            from_map = path[i]
            to_map = path[i + 1]
            
            if not self._walk_to_adjacent_map(from_map, to_map):
                logger.error(f"无法从 {from_map} 前往 {to_map}")
                return False
            
            time.sleep(2.0)
        
        logger.info(f"成功到达 {target_map}")
        return True

    def _calculate_path(self, start: str, end: str) -> List[str]:
        if start == end:
            return [start]
        
        from collections import deque
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            if current == end:
                return path
            
            if current in self.map_connections:
                for next_map in self.map_connections[current]:
                    if next_map not in visited:
                        visited.add(next_map)
                        queue.append((next_map, path + [next_map]))
        
        return []

    def _walk_to_adjacent_map(self, from_map: str, to_map: str) -> bool:
        logger.info(f"从 {from_map} 步行到 {to_map}")
        
        if from_map not in self.map_connections or to_map not in self.map_connections[from_map]:
            return False
        
        connection_coords = self.map_connections[from_map][to_map]
        
        self.move_to_coordinate(connection_coords[0], connection_coords[1])
        time.sleep(3.0)
        
        new_map = self.detect_current_map()
        return new_map == to_map

    def move_to_coordinate(self, x: int, y: int) -> bool:
        logger.info(f"移动到坐标: ({x}, {y})")
        
        self.window_manager.click_game_coords(x, y, duration=0.2)
        time.sleep(1.0)
        
        self.current_coords = (x, y)
        return True

    def use_teleport_method(self, method: str, target_map: str) -> bool:
        logger.info(f"使用 {method} 前往 {target_map}")
        
        if method == "飞行符":
            return self._use_fly_symbol(target_map)
        elif method == "导标旗":
            return self._use_guide_flag(target_map)
        elif method == "驿站":
            return self._use_station_transport(target_map)
        elif method == "傲来驿站":
            self.teleport_to("傲来国")
            time.sleep(1.0)
            return self._use_station_transport(target_map)
        elif method == "长安驿站":
            self.teleport_to("长安城")
            time.sleep(1.0)
            return self._use_station_transport(target_map)
        elif method == "傲来导标旗":
            return self._use_guide_flag(target_map)
        elif method == "大唐国境传送":
            self.teleport_to("大唐国境")
            time.sleep(1.0)
            return self.walk_to_map(target_map)
        else:
            logger.warning(f"未知的传送方式: {method}")
            return False

    def get_current_position(self) -> Tuple[str, Tuple[int, int]]:
        current_map = self.detect_current_map()
        return (current_map, self.current_coords)

    def is_at_location(self, map_name: str, x: int = None, y: int = None, tolerance: int = 50) -> bool:
        current_map = self.detect_current_map()
        
        if current_map != map_name:
            return False
        
        if x is not None and y is not None:
            dx = abs(self.current_coords[0] - x)
            dy = abs(self.current_coords[1] - y)
            return dx <= tolerance and dy <= tolerance
        
        return True
