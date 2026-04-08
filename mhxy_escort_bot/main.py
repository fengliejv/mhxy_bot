"""
梦幻西游 Escort Automation Bot
Main controller module for automating the Escort (押镖) gameplay
"""

import time
import cv2
import numpy as np
import pyautogui
import win32gui
import win32con
from PIL import ImageGrab
import logging
import os
from typing import Tuple, Optional, Dict, Any

from .config import GAME_WINDOW_TITLE, SAFETY_SETTINGS, LOGGING_CONFIG


class MHXYEscortBot:
    def __init__(self):
        self.game_window = None
        self.running = False
        self.current_state = "idle"
        
        # 设置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # 初始化截图区域（相对于窗口）
        self.screenshot_region = None
        
        # 导入其他模块
        from .npc_interaction import NPCInteraction
        from .navigation import NavigationSystem
        from .combat import CombatSystem
        from .inventory import InventoryManager
        
        # 初始化子系统
        self.npc_interaction = NPCInteraction(self)
        self.navigation_system = NavigationSystem(self)
        self.combat_system = CombatSystem(self)
        self.inventory_manager = InventoryManager(self)
        
    def find_game_window(self) -> bool:
        """
        查找梦幻西游游戏窗口
        """
        try:
            # 尝试找到梦幻西游窗口
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if GAME_WINDOW_TITLE in window_title:
                        windows.append((hwnd, window_title))
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            for hwnd, title in windows:
                self.logger.info(f"Found window: {title} (Handle: {hwnd})")
                if GAME_WINDOW_TITLE in title:
                    self.game_window = hwnd
                    self.logger.info(f"Found 梦幻西游 window: {title}")
                    
                    # 获取窗口位置和大小
                    rect = win32gui.GetWindowRect(hwnd)
                    self.screenshot_region = (rect[0], rect[1], rect[2], rect[3])
                    self.logger.info(f"Window region: {self.screenshot_region}")
                    return True
            
            self.logger.error(f"未找到{GAME_WINDOW_TITLE}窗口")
            return False
            
        except Exception as e:
            self.logger.error(f"查找游戏窗口时出错: {e}")
            return False
    
    def activate_window(self) -> bool:
        """
        激活游戏窗口
        """
        if not self.game_window:
            if not self.find_game_window():
                return False
        
        try:
            # 将窗口前置并激活
            win32gui.SetForegroundWindow(self.game_window)
            win32gui.ShowWindow(self.game_window, win32con.SW_RESTORE)
            time.sleep(0.5)  # 等待窗口激活
            return True
        except Exception as e:
            self.logger.error(f"激活窗口时出错: {e}")
            return False
    
    def capture_screen(self) -> Optional[np.ndarray]:
        """
        截取游戏画面
        """
        if not self.screenshot_region:
            self.logger.error("截图区域未定义")
            return None
        
        try:
            # 截图
            screenshot = ImageGrab.grab(bbox=self.screenshot_region)
            # 转换为numpy数组
            frame = np.array(screenshot)
            # 转换颜色格式 (PIL使用RGB, OpenCV使用BGR)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame
        except Exception as e:
            self.logger.error(f"截图失败: {e}")
            return None
    
    def detect_game_state(self) -> str:
        """
        检测当前游戏状态
        返回状态类型如: 'in_tavern', 'on_map', 'in_combat', 'idle'
        """
        screen = self.capture_screen()
        if screen is None:
            return "unknown"
        
        # 这里可以添加更复杂的状态检测逻辑
        # 比如检测特定UI元素、NPC头像、战斗界面等
        
        # 简单示例：检测是否在酒馆（寻找特定颜色或图案）
        # 实际应用中需要训练模型或使用模板匹配
        return "idle"
    
    def locate_npc(self, npc_name: str) -> Optional[Tuple[int, int]]:
        """
        定位NPC位置
        """
        screen = self.capture_screen()
        if screen is None:
            return None
        
        # 这里需要实现图像识别来定位NPC
        # 可以使用模板匹配或其他计算机视觉技术
        # 示例：寻找酒馆店小二
        if npc_name == "酒馆店小二":
            # 实现具体的NPC定位逻辑
            pass
        
        return None
    
    def click_position(self, x: int, y: int, delay: float = 0.5):
        """
        点击指定位置
        """
        if self.activate_window():
            # 计算绝对坐标
            abs_x = self.screenshot_region[0] + x
            abs_y = self.screenshot_region[1] + y
            
            pyautogui.click(abs_x, abs_y)
            time.sleep(delay)
    
    def move_to_location(self, x: int, y: int):
        """
        移动到指定位置
        """
        if self.activate_window():
            # 计算绝对坐标
            abs_x = self.screenshot_region[0] + x
            abs_y = self.screenshot_region[1] + y
            
            pyautogui.moveTo(abs_x, abs_y)
            pyautogui.click()
    
    def start_escort_process(self):
        """
        开始押镖流程
        """
        self.logger.info("开始押镖流程")
        self.running = True
        
        escort_step = "find_npc"  # 当前押镖步骤: find_npc, travel, combat, return_npc
        
        while self.running:
            current_state = self.detect_game_state()
            self.logger.info(f"当前状态: {current_state}, 步骤: {escort_step}")
            
            # 管理资源和状态
            self.inventory_manager.manage_resources_during_escort()
            
            if escort_step == "find_npc":
                # 寻找酒馆店小二并获取任务
                self.get_escort_task()
                # 检查是否成功获取任务，如果是则进入旅行阶段
                if current_state in ["on_map", "traveling"]:
                    escort_step = "travel"
                time.sleep(2)
                
            elif escort_step == "travel":
                # 前往押镖目的地
                self.navigate_to_destination()
                # 检查是否到达目的地并遇到强盗
                if self.combat_system.detect_combat_status():
                    escort_step = "combat"
                time.sleep(2)
                
            elif escort_step == "combat":
                # 与强盗战斗
                self.fight_bandits()
                # 战斗结束后返回酒馆交任务
                escort_step = "return_npc"
                time.sleep(2)
                
            elif escort_step == "return_npc":
                # 返回酒馆店小二处交任务
                success = self.npc_interaction.return_to_npc_for_completion()
                if success:
                    # 完成一轮押镖，重新开始
                    escort_step = "find_npc"
                time.sleep(2)
            
            time.sleep(1)  # 暂停1秒再检查状态
    
    def get_escort_task(self):
        """
        获取押镖任务
        """
        self.logger.info("寻找酒馆店小二...")
        
        # 使用NPC交互模块获取任务
        success = self.npc_interaction.get_escort_task_from_npc()
        if success:
            self.logger.info("成功获取押镖任务")
            # 更新状态为在地图上，准备前往目的地
            time.sleep(2)  # 等待任务信息加载
        else:
            self.logger.warning("获取押镖任务失败")
    
    def accept_escort_task(self):
        """
        接受押镖任务
        """
        self.logger.info("接受押镖任务...")
        # 这个方法与get_escort_task合并了功能，可以留空或作为辅助方法
        pass
    
    def navigate_to_destination(self):
        """
        导航到目的地
        """
        self.logger.info("导航到目的地...")
        
        # 使用导航系统前往目的地
        # 这里需要从任务信息中提取目的地
        # 为了演示，假设目的地是"建邺城"
        self.navigation_system.set_destination("建邺城")
        success = self.navigation_system.navigate_to_destination()
        
        if success:
            self.logger.info("成功到达目的地")
        else:
            self.logger.warning("导航到目的地失败")
    
    def fight_bandits(self):
        """
        击败强盗
        """
        self.logger.info("击败强盗...")
        
        # 使用战斗系统进行战斗
        success = self.combat_system.engage_combat()
        
        if success:
            self.logger.info("成功击败强盗")
        else:
            self.logger.warning("战斗失败或超时")
    
    def stop(self):
        """
        停止机器人
        """
        self.running = False
        self.logger.info("押镖机器人已停止")


def main():
    bot = MHXYEscortBot()
    
    if bot.find_game_window():
        print("成功找到梦幻西游窗口")
        bot.start_escort_process()
    else:
        print("未找到梦幻西游窗口，请确保游戏已启动")


if __name__ == "__main__":
    main()