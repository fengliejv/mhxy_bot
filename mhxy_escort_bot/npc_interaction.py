"""
NPC交互模块
处理与游戏内NPC的交互，特别是酒馆店小二
"""

import time
import cv2
import numpy as np
from typing import Tuple, Optional
from .image_recognition import ImageRecognition
from .main import MHXYEscortBot


class NPCInteraction:
    def __init__(self, bot: MHXYEscortBot):
        self.bot = bot
        self.image_recognition = ImageRecognition()
        
        # 预设的酒馆店小二特征
        self.tavern_npc_colors = [
            ((0, 50, 50), (10, 255, 255)),      # 红色调
            ((100, 50, 50), (130, 255, 255)),   # 蓝色调
            ((20, 50, 50), (30, 255, 255)),     # 黄色调
        ]
        
        # 酒馆店小二的可能模板（需要在游戏中截取实际图片）
        # self.load_npc_templates()
    
    def find_tavern_npc(self) -> Optional[Tuple[int, int]]:
        """
        寻找酒馆店小二
        """
        screen = self.bot.capture_screen()
        if screen is None:
            return None
        
        # 方法1: 通过颜色检测
        for color_range in self.tavern_npc_colors:
            lower, upper = color_range
            npc_pos = self.image_recognition.detect_color_region(screen, lower, upper)
            if npc_pos:
                self.bot.logger.info(f"通过颜色检测找到NPC位置: {npc_pos}")
                return npc_pos
        
        # 方法2: 通过模板匹配（如果有预存的模板）
        # 这里需要预先准备酒馆店小二的图片模板
        # for name, template in self.image_recognition.templates.items():
        #     pos = self.image_recognition.find_template_on_screen(screen, template)
        #     if pos:
        #         self.bot.logger.info(f"通过模板匹配找到NPC位置: ({pos[0]}, {pos[1]})")
        #         return (pos[0], pos[1])
        
        # 方法3: 如果在酒馆场景，NPC通常在固定位置
        # 根据游戏场景特点，酒馆店小二通常在特定位置
        # 这里可以根据实际游戏情况调整坐标
        tavern_areas = [
            (screen.shape[1] // 3, screen.shape[0] // 2),  # 左侧中间
            (2 * screen.shape[1] // 3, screen.shape[0] // 2),  # 右侧中间
            (screen.shape[1] // 2, screen.shape[0] // 3),  # 中上
        ]
        
        # 检查这些区域是否有明显的NPC特征
        for x, y in tavern_areas:
            # 检查该区域是否有NPC特有的颜色或形状
            roi = screen[max(0, y-50):min(screen.shape[0], y+50), 
                         max(0, x-50):min(screen.shape[1], x+50)]
            
            # 简单判断：如果区域内有多种颜色且有一定复杂度，可能是NPC
            if self.is_likely_npc_region(roi):
                self.bot.logger.info(f"在预设区域发现可能的NPC: ({x}, {y})")
                return (x, y)
        
        return None
    
    def is_likely_npc_region(self, roi) -> bool:
        """
        判断区域是否可能是NPC
        """
        if roi.size == 0:
            return False
        
        # 计算区域的颜色方差，NPC通常颜色较丰富
        color_variance = np.var(roi.reshape(-1, roi.shape[-1]), axis=0).mean()
        
        # 计算边缘数量，NPC通常有较多细节
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # 如果颜色变化丰富且有足够多的边缘，则认为可能是NPC
        return color_variance > 1000 and edge_density > 0.05
    
    def interact_with_npc(self, npc_pos: Tuple[int, int]):
        """
        与NPC交互
        """
        x, y = npc_pos
        self.bot.logger.info(f"与NPC交互，位置: ({x}, {y})")
        
        # 点击NPC位置
        self.bot.click_position(x, y, delay=1.0)
        
        # 等待对话框出现
        time.sleep(1.0)
        
        # 在梦幻西游中，通常需要再次点击对话框继续
        # 或者按空格键继续对话
        center_x = self.bot.screenshot_region[2] - self.bot.screenshot_region[0] // 2
        center_y = self.bot.screenshot_region[3] - self.bot.screenshot_region[1] // 2
        self.bot.click_position(center_x, center_y, delay=1.0)
    
    def get_escort_task_from_npc(self) -> bool:
        """
        从酒馆店小二处获取押镖任务
        """
        self.bot.logger.info("尝试从酒馆店小二处获取押镖任务")
        
        # 寻找酒馆店小二
        npc_pos = self.find_tavern_npc()
        if not npc_pos:
            self.bot.logger.warning("未找到酒馆店小二")
            return False
        
        # 与NPC交互
        self.interact_with_npc(npc_pos)
        
        # 等待对话选项出现，通常需要选择押镖任务
        time.sleep(2.0)
        
        # 在对话选项中选择押镖（通常是第一个或第二个选项）
        # 这里需要根据实际游戏界面调整点击位置
        screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
        screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
        
        # 假设对话选项出现在屏幕下方
        option_x = screen_width // 2
        option_y = int(screen_height * 0.8)
        
        self.bot.click_position(option_x, option_y, delay=1.0)
        
        # 等待任务确认
        time.sleep(2.0)
        
        # 检查是否成功接取任务
        # 这里可以通过检测任务界面或系统消息来确认
        if self.check_task_accepted():
            self.bot.logger.info("成功获取押镖任务")
            return True
        else:
            self.bot.logger.warning("获取押镖任务失败")
            return False
    
    def check_task_accepted(self) -> bool:
        """
        检查是否已接受任务
        """
        # 这里需要实现任务状态检测逻辑
        # 可以通过检测任务栏、系统消息或其他UI元素来判断
        screen = self.bot.capture_screen()
        if screen is None:
            return False
        
        # 示例：检测是否有任务相关的UI元素
        # 实际实现需要根据游戏界面调整
        return True  # 简化实现，实际需要具体检测逻辑
    
    def return_to_npc_for_completion(self) -> bool:
        """
        返回到NPC处完成任务
        """
        self.bot.logger.info("返回酒馆店小二处完成任务")
        
        # 寻找酒馆店小二
        npc_pos = self.find_tavern_npc()
        if not npc_pos:
            self.bot.logger.warning("未找到酒馆店小二")
            return False
        
        # 与NPC交互
        self.interact_with_npc(npc_pos)
        
        # 等待对话选项，选择完成任务
        time.sleep(2.0)
        
        # 点击完成任务选项
        screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
        screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
        
        option_x = screen_width // 2
        option_y = int(screen_height * 0.8)
        
        self.bot.click_position(option_x, option_y, delay=1.0)
        
        # 等待任务完成反馈
        time.sleep(2.0)
        
        # 检查任务是否完成
        if self.check_task_completed():
            self.bot.logger.info("成功完成押镖任务")
            return True
        else:
            self.bot.logger.warning("完成押镖任务失败")
            return False
    
    def check_task_completed(self) -> bool:
        """
        检查任务是否已完成
        """
        # 检测任务完成的标志
        screen = self.bot.capture_screen()
        if screen is None:
            return False
        
        # 实现具体的任务完成检测逻辑
        return True  # 简化实现