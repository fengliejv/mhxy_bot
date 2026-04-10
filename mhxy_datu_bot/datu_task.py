"""
梦幻西游打图自动化 - 打图任务模块
处理打图任务的领取、解析、执行和完成
"""

import time
import re
import cv2
import numpy as np
import pyautogui
from typing import Dict, Optional, Tuple, List
from .config import (
    HOTEL_ENTRANCE_COORDS,
    SHOP_WAITER_NAME,
    SHOP_WAITER_DIALOG_OPTION,
    TASK_COST_SILVER,
    BANDIT_MAPS,
    MAX_DAILY_TASKS,
    SANJIE_FREE_TASKS,
    SANJIE_COST_PER_TASK,
    SANJIE_MIN_THRESHOLD,
    KEY_SHORTCUTS,
)
from .logger import setup_logger

logger = setup_logger("datu_task")


class DatuTask:
    def __init__(self, window_manager, image_recognition, navigation_system, combat_system, npc_interaction):
        self.window_manager = window_manager
        self.image_recognition = image_recognition
        self.navigation = navigation_system
        self.combat = combat_system
        self.npc = npc_interaction
        
        self.current_task = None
        self.task_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.sanjie_points = 0
        
        self.task_history = []

    def go_to_hotel(self) -> bool:
        logger.info("前往长安酒店")
        
        hotel_entrance = HOTEL_ENTRANCE_COORDS
        success = self.navigation.teleport_to("长安城")
        
        if not success:
            logger.error("无法传送到长安城")
            return False
        
        time.sleep(1.0)
        
        self.window_manager.click_game_coords(hotel_entrance[0], hotel_entrance[1])
        time.sleep(2.0)
        
        logger.info("已到达长安酒店")
        return True

    def accept_task_from_waiter(self) -> bool:
        logger.info("从店小二领取打图任务")
        
        waiter_pos = self.npc.find_npc(SHOP_WAITER_NAME)
        if waiter_pos is None:
            logger.warning("未找到店小二，尝试默认位置")
            waiter_pos = (460, 164)
        
        self.window_manager.click_game_coords(waiter_pos[0], waiter_pos[1])
        time.sleep(1.0)
        
        dialog_option_pos = self._find_dialog_option(SHOP_WAITER_DIALOG_OPTION)
        if dialog_option_pos:
            self.window_manager.click_game_coords(dialog_option_pos[0], dialog_option_pos[1])
        else:
            default_option_pos = (self.window_manager.window_rect[2] // 2, 
                                  self.window_manager.window_rect[3] * 3 // 4)
            self.window_manager.click_game_coords(default_option_pos[0], default_option_pos[1])
        
        time.sleep(1.0)
        
        self.task_count += 1
        logger.info(f"成功领取打图任务 (第 {self.task_count} 次)")
        return True

    def _find_dialog_option(self, option_text: str) -> Optional[Tuple[int, int]]:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        dialog_region = (200, 400, 600, 600)
        dialog_area = screenshot[dialog_region[1]:dialog_region[3], dialog_region[0]:dialog_region[2]]
        
        text = self.image_recognition.detect_text_region(dialog_area)
        if text and option_text in text:
            return (dialog_region[0] + 200, dialog_region[1] + 100)
        
        return None

    def parse_task_info(self) -> Optional[Dict]:
        logger.info("解析任务信息")
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        task_region = (200, 100, 600, 200)
        task_area = screenshot[task_region[1]:task_region[3], task_region[0]:task_region[2]]
        
        task_text = self.image_recognition.detect_text_region(task_area)
        
        if task_text:
            task_info = self._extract_task_details(task_text)
            if task_info:
                self.current_task = task_info
                logger.info(f"任务信息: 地图={task_info['map']}, 坐标=({task_info['x']}, {task_info['y']})")
                return task_info
        
        logger.warning("无法解析任务信息，使用默认值")
        default_task = {
            "map": "大唐国境",
            "x": 200,
            "y": 100,
            "bandit_name": "强盗",
        }
        self.current_task = default_task
        return default_task

    def _extract_task_details(self, text: str) -> Optional[Dict]:
        map_pattern = r"在(.*?)出现"
        coord_pattern = r"坐标[：:]\s*(\d+)[,，]\s*(\d+)"
        
        map_match = re.search(map_pattern, text)
        coord_match = re.search(coord_pattern, text)
        
        task_info = {}
        
        if map_match:
            task_info["map"] = map_match.group(1).strip()
        else:
            for map_name in BANDIT_MAPS.keys():
                if map_name in text:
                    task_info["map"] = map_name
                    break
        
        if coord_match:
            task_info["x"] = int(coord_match.group(1))
            task_info["y"] = int(coord_match.group(2))
        else:
            if "map" in task_info and task_info["map"] in BANDIT_MAPS:
                coords_list = BANDIT_MAPS[task_info["map"]]["coords"]
                task_info["x"] = coords_list[0][0]
                task_info["y"] = coords_list[0][1]
        
        if "map" in task_info and "x" in task_info:
            task_info["bandit_name"] = "强盗"
            return task_info
        
        return None

    def travel_to_bandit(self, task_info: Dict) -> bool:
        logger.info(f"前往强盗位置: {task_info['map']} ({task_info['x']}, {task_info['y']})")
        
        target_map = task_info["map"]
        target_x = task_info["x"]
        target_y = task_info["y"]
        
        if target_map in BANDIT_MAPS:
            teleport_method = BANDIT_MAPS[target_map]["teleport"]
            logger.info(f"使用 {teleport_method} 前往 {target_map}")
            
            success = self.navigation.use_teleport_method(teleport_method, target_map)
            if not success:
                logger.warning("传送失败，尝试步行")
                success = self.navigation.walk_to_map(target_map)
            
            if not success:
                logger.error(f"无法到达 {target_map}")
                return False
        else:
            logger.warning(f"未知地图: {target_map}，尝试默认导航")
            success = self.navigation.walk_to_map(target_map)
            if not success:
                return False
        
        time.sleep(1.0)
        
        self.navigation.move_to_coordinate(target_x, target_y)
        time.sleep(2.0)
        
        logger.info(f"已到达强盗位置附近")
        return True

    def find_and_fight_bandit(self) -> bool:
        logger.info("寻找并挑战强盗")
        
        bandit_pos = self._find_bandit()
        if bandit_pos is None:
            logger.warning("未找到强盗，尝试在附近搜索")
            bandit_pos = self._search_nearby_for_bandit()
        
        if bandit_pos is None:
            logger.error("无法找到强盗")
            return False
        
        self.window_manager.click_game_coords(bandit_pos[0], bandit_pos[1])
        time.sleep(1.0)
        
        fight_option_pos = self._find_fight_option()
        if fight_option_pos:
            self.window_manager.click_game_coords(fight_option_pos[0], fight_option_pos[1])
        else:
            default_pos = (self.window_manager.window_rect[2] // 2,
                          self.window_manager.window_rect[3] * 3 // 4)
            self.window_manager.click_game_coords(default_pos[0], default_pos[1])
        
        time.sleep(1.0)
        
        logger.info("进入战斗")
        combat_result = self.combat.start_combat()
        
        return combat_result

    def _find_bandit(self) -> Optional[Tuple[int, int]]:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        
        bandit_colors = [
            ((0, 50, 50), (20, 255, 255)),
            ((100, 50, 50), (130, 255, 255)),
        ]
        
        for lower, upper in bandit_colors:
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

    def _search_nearby_for_bandit(self) -> Optional[Tuple[int, int]]:
        search_offsets = [(50, 0), (-50, 0), (0, 50), (0, -50), (50, 50), (-50, -50)]
        
        for dx, dy in search_offsets:
            if self.current_task:
                new_x = self.current_task["x"] + dx
                new_y = self.current_task["y"] + dy
                self.navigation.move_to_coordinate(new_x, new_y)
                time.sleep(1.0)
                
                bandit_pos = self._find_bandit()
                if bandit_pos:
                    return bandit_pos
        
        return None

    def _find_fight_option(self) -> Optional[Tuple[int, int]]:
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return None
        
        dialog_region = (200, 400, 600, 600)
        dialog_area = screenshot[dialog_region[1]:dialog_region[3], dialog_region[0]:dialog_region[2]]
        
        text = self.image_recognition.detect_text_region(dialog_area)
        if text and "收拾" in text:
            return (dialog_region[0] + 200, dialog_region[1] + 100)
        
        return None

    def check_treasure_map_reward(self) -> bool:
        logger.info("检查是否获得藏宝图")
        
        time.sleep(2.0)
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            return False
        
        reward_region = (300, 300, 500, 400)
        reward_area = screenshot[reward_region[1]:reward_region[3], reward_region[0]:reward_region[2]]
        
        text = self.image_recognition.detect_text_region(reward_area)
        
        if text and "藏宝图" in text:
            self.success_count += 1
            logger.info(f"获得藏宝图! 成功次数: {self.success_count}")
            return True
        
        logger.info("未获得藏宝图")
        return False

    def return_to_hotel(self) -> bool:
        logger.info("返回长安酒店")
        
        success = self.navigation.teleport_to("长安城")
        if not success:
            logger.warning("传送失败，尝试其他方式")
            return False
        
        time.sleep(1.0)
        
        hotel_entrance = HOTEL_ENTRANCE_COORDS
        self.window_manager.click_game_coords(hotel_entrance[0], hotel_entrance[1])
        time.sleep(2.0)
        
        logger.info("已返回长安酒店")
        return True

    def check_sanjie_points(self) -> int:
        logger.info("检查三界功绩")
        
        pyautogui.hotkey("alt", "q")
        time.sleep(1.0)
        
        screenshot = self.window_manager.capture_screen()
        if screenshot is None:
            pyautogui.press("esc")
            return 0
        
        sanjie_region = (700, 50, 900, 100)
        sanjie_area = screenshot[sanjie_region[1]:sanjie_region[3], sanjie_region[0]:sanjie_region[2]]
        
        text = self.image_recognition.detect_text_region(sanjie_area)
        
        pyautogui.press("esc")
        time.sleep(0.3)
        
        if text:
            match = re.search(r"(\d+)", text)
            if match:
                self.sanjie_points = int(match.group(1))
                logger.info(f"三界功绩: {self.sanjie_points}")
                return self.sanjie_points
        
        return 0

    def is_sanjie_sufficient(self) -> bool:
        points = self.check_sanjie_points()
        
        if self.task_count < SANJIE_FREE_TASKS:
            return True
        
        required_points = (self.task_count - SANJIE_FREE_TASKS + 1) * SANJIE_COST_PER_TASK
        return points >= required_points

    def execute_single_task(self) -> bool:
        logger.info(f"开始执行第 {self.task_count + 1} 次打图任务")
        
        if not self.go_to_hotel():
            logger.error("无法到达酒店")
            return False
        
        if not self.accept_task_from_waiter():
            logger.error("无法领取任务")
            return False
        
        task_info = self.parse_task_info()
        if not task_info:
            logger.error("无法解析任务信息")
            return False
        
        if not self.travel_to_bandit(task_info):
            logger.error("无法到达强盗位置")
            self.fail_count += 1
            return False
        
        if not self.find_and_fight_bandit():
            logger.error("战斗失败")
            self.fail_count += 1
            return False
        
        got_treasure = self.check_treasure_map_reward()
        
        if not self.return_to_hotel():
            logger.warning("返回酒店失败，但任务已完成")
        
        task_record = {
            "task_num": self.task_count,
            "map": task_info["map"],
            "coords": (task_info["x"], task_info["y"]),
            "success": got_treasure,
            "timestamp": time.time(),
        }
        self.task_history.append(task_record)
        
        logger.info(f"任务完成: {'成功' if got_treasure else '失败'}")
        return True

    def get_statistics(self) -> Dict:
        return {
            "total_tasks": self.task_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": self.success_count / max(1, self.task_count) * 100,
            "sanjie_points": self.sanjie_points,
        }
