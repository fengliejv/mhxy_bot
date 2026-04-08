"""
战斗系统模块
处理与押镖过程中遇到的强盗战斗
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Tuple, Optional, List
from .main import MHXYEscortBot
import logging


class CombatSystem:
    def __init__(self, bot: MHXYEscortBot):
        self.bot = bot
        self.in_combat = False
        self.enemy_count = 0
        self.player_hp_percent = 100
        self.player_mp_percent = 100
        
        # 技能快捷键配置（需要根据玩家实际设置调整）
        self.skill_shortcuts = {
            'attack': '1',      # 普通攻击
            'skill1': '2',      # 第一个技能
            'skill2': '3',      # 第二个技能
            'skill3': '4',      # 第三个技能
            'defend': '5',      # 防御
            'use_item': '6',    # 使用药品
        }
        
        # 药品快捷键配置
        self.item_shortcuts = {
            'red_potion': 'F1',  # 生命药水
            'blue_potion': 'F2', # 法力药水
        }
    
    def detect_combat_status(self) -> bool:
        """
        检测是否处于战斗状态
        """
        screen = self.bot.capture_screen()
        if screen is None:
            return False
        
        # 检测战斗界面特征：
        # 1. 战斗界面边框
        # 2. 血条
        # 3. 战斗操作按钮
        # 4. 敌人头像
        
        # 检测战斗界面底部的操作栏
        bottom_region = screen[int(screen.shape[0] * 0.8):, :]
        
        # 检测是否有战斗特有的颜色模式
        hsv = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2HSV)
        
        # 检测战斗界面常见的UI颜色（需要根据实际游戏调整）
        ui_colors = [
            ((0, 0, 100), (180, 50, 200)),  # 深色UI背景
            ((0, 50, 50), (20, 255, 255)),   # 红色元素
            ((100, 50, 50), (130, 255, 255)), # 蓝色元素
        ]
        
        for lower, upper in ui_colors:
            mask = cv2.inRange(hsv, lower, upper)
            if np.sum(mask) > bottom_region.shape[0] * bottom_region.shape[1] * 0.1:  # 如果特定颜色占比超过10%
                return True
        
        # 检测敌人头像区域（通常在屏幕右侧）
        right_region = screen[:, int(screen.shape[1] * 0.7):]
        enemy_avatar_detected = self.detect_enemy_avatars(right_region)
        
        # 尝试导入视觉大模型适配器以增强检测
        try:
            from .treasure_hunt import TreasureHuntSystem
            # 如果TreasureHuntSystem可用，尝试获取其视觉适配器
            # 由于循环导入问题，我们直接尝试导入VisionModelAdapter
            from .vision_adapter import VisionModelAdapter
            # 如果有视觉适配器实例，可以使用它来确认战斗状态
            # 但在这里我们只使用传统方法，因为无法直接访问TreasureHuntSystem实例
        except ImportError:
            pass
        
        return enemy_avatar_detected
    
    def detect_enemy_avatars(self, region) -> bool:
        """
        检测敌人头像
        """
        # 检测可能的敌人头像特征
        # 通常是圆形头像框和特定颜色
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # 尝试检测圆形（头像框）
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
            return True
        
        return False
    
    def detect_player_status(self):
        """
        检测玩家状态（血量、法力等）
        """
        screen = self.bot.capture_screen()
        if screen is None:
            return
        
        # 检测玩家血条和蓝条
        # 通常在屏幕左下角
        left_bottom_region = screen[int(screen.shape[0] * 0.8):, :int(screen.shape[1] * 0.3)]
        
        # 检测红色血条
        hsv = cv2.cvtColor(left_bottom_region, cv2.COLOR_BGR2HSV)
        red_mask = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
        
        # 计算血条长度比例
        if np.any(red_mask):
            # 简化的血量检测
            total_width = left_bottom_region.shape[1]
            hp_pixels = np.sum(np.any(red_mask, axis=0))  # 统计有红色像素的列数
            self.player_hp_percent = min(100, int((hp_pixels / total_width) * 100))
        
        # 检测蓝色法力条
        blue_mask = cv2.inRange(hsv, (100, 100, 100), (130, 255, 255))
        if np.any(blue_mask):
            total_width = left_bottom_region.shape[1]
            mp_pixels = np.sum(np.any(blue_mask, axis=0))
            self.player_mp_percent = min(100, int((mp_pixels / total_width) * 100))
    
    def detect_enemies(self) -> List[Tuple[int, int, str]]:
        """
        检测敌人位置和类型
        """
        screen = self.bot.capture_screen()
        if screen is None:
            return []
        
        enemies = []
        
        # 检测敌人位置（通常在屏幕上方或中央偏右）
        upper_region = screen[:int(screen.shape[0] * 0.7), int(screen.shape[1] * 0.3):]
        
        # 检测敌人的颜色特征（通常为红色或其他醒目的颜色）
        hsv = cv2.cvtColor(upper_region, cv2.COLOR_BGR2HSV)
        
        # 定义敌人可能的颜色范围
        enemy_colors = [
            ((0, 50, 50), (20, 255, 255)),    # 红色敌人
            ((0, 100, 100), (10, 255, 255)),  # 鲜红色敌人
        ]
        
        for lower, upper in enemy_colors:
            mask = cv2.inRange(hsv, lower, upper)
            
            # 查找连通区域
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 300:  # 过滤小面积噪声
                    # 计算轮廓中心
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        # 计算在upper_region中的相对坐标
                        rel_cx = int(M["m10"] / M["m00"])
                        rel_cy = int(M["m01"] / M["m00"])
                        
                        # 转换为全局坐标
                        cx = rel_cx + int(screen.shape[1] * 0.3)  # 加上区域偏移
                        cy = rel_cy
                        
                        # 边界检查
                        if 0 <= rel_cy < mask.shape[0] and 0 <= rel_cx < mask.shape[1]:
                            # 判断敌人类型（根据颜色和形状）
                            enemy_type = self.classify_enemy(mask[rel_cy, rel_cx])
                        else:
                            enemy_type = "normal"  # 默认类型
                            
                        enemies.append((cx, cy, enemy_type))
        
        return enemies
    
    def classify_enemy(self, pixel_value) -> str:
        """
        分类敌人类型
        """
        # 简化的敌人分类
        if pixel_value > 200:
            return "normal"
        else:
            return "strong"
    
    def engage_combat(self) -> bool:
        """
        参与战斗
        """
        self.bot.logger.info("进入战斗模式")
        self.in_combat = True
        
        battle_round = 0
        max_rounds = 100  # 增加最大回合数，给视觉模型更多时间检测战斗结束
        
        while self.in_combat and battle_round < max_rounds:
            # 更新战斗状态 - 使用更精确的检测方法
            self.in_combat = self.detect_combat_status()
            
            # 检测玩家状态
            self.detect_player_status()
            
            # 检查是否需要补充状态
            self.manage_status()
            
            # 执行战斗策略
            self.execute_combat_strategy()
            
            # 每隔几轮额外检测一次战斗状态
            if battle_round % 5 == 0:
                # 尝试使用更全面的战斗状态检测
                if hasattr(self.bot, 'treasure') and hasattr(self.bot.treasure, 'vision_adapter'):
                    screen = self.bot.capture_screen()
                    if screen is not None:
                        # 使用视觉大模型检测战斗状态
                        vision_in_combat = self.bot.treasure.vision_adapter.detect_combat_status_vision(screen)
                        if not vision_in_combat:
                            self.bot.logger.info("视觉大模型检测到战斗已结束")
                            self.in_combat = False
                            break
            
            battle_round += 1
            time.sleep(0.8)  # 稍微加快检测频率
        
        if battle_round >= max_rounds:
            self.bot.logger.warning("战斗超时，可能卡住了")
            return False
        
        self.bot.logger.info("战斗结束")
        return True
    
    def manage_status(self):
        """
        管理玩家状态（血量、法力等）
        """
        # 检查血量，如果低于阈值则使用药品
        if self.player_hp_percent < 50:
            self.use_health_potion()
        
        # 检查法力，如果需要则使用蓝药
        if self.player_mp_percent < 30:
            self.use_mana_potion()
    
    def use_health_potion(self):
        """
        使用生命药水
        """
        if 'red_potion' in self.item_shortcuts:
            pyautogui.press(self.item_shortcuts['red_potion'])
            self.bot.logger.info("使用生命药水")
            time.sleep(0.5)
    
    def use_mana_potion(self):
        """
        使用法力药水
        """
        if 'blue_potion' in self.item_shortcuts:
            pyautogui.press(self.item_shortcuts['blue_potion'])
            self.bot.logger.info("使用法力药水")
            time.sleep(0.5)
    
    def execute_combat_strategy(self):
        """
        执行战斗策略
        """
        # 检测敌人
        enemies = self.detect_enemies()
        
        if not enemies:
            # 如果没有检测到敌人但仍在战斗中，可能需要点击攻击按钮
            pyautogui.press(self.skill_shortcuts['attack'])
            return
        
        # 优先攻击最近的敌人
        closest_enemy = self.find_closest_enemy(enemies)
        if closest_enemy:
            enemy_x, enemy_y, enemy_type = closest_enemy
            
            # 根据敌人类型选择技能
            if enemy_type == "strong":
                # 对强敌使用强力技能
                self.use_skill('skill2')
            else:
                # 对普通敌人使用普通攻击或常规技能
                self.use_skill('attack')
    
    def find_closest_enemy(self, enemies: List[Tuple[int, int, str]]) -> Optional[Tuple[int, int, str]]:
        """
        找到最近的敌人
        """
        if not enemies:
            return None
        
        # 计算到屏幕中心的距离
        center_x = (self.bot.screenshot_region[2] - self.bot.screenshot_region[0]) // 2
        center_y = (self.bot.screenshot_region[3] - self.bot.screenshot_region[1]) // 2
        
        closest = min(enemies, key=lambda e: (e[0] - center_x)**2 + (e[1] - center_y)**2)
        return closest
    
    def use_skill(self, skill_name: str):
        """
        使用技能
        """
        if skill_name in self.skill_shortcuts:
            pyautogui.press(self.skill_shortcuts[skill_name])
            self.bot.logger.info(f"使用技能: {skill_name}")
            time.sleep(0.3)  # 技能释放间隔
    
    def auto_attack_sequence(self):
        """
        自动攻击序列
        """
        # 连续攻击直到战斗结束
        while self.detect_combat_status():
            # 使用主要攻击技能
            pyautogui.press(self.skill_shortcuts['attack'])
            time.sleep(1.0)
            
            # 偶尔使用其他技能
            if time.time() % 5 < 1:  # 每5秒使用一次特殊技能
                self.use_skill('skill1')
    
    def flee_combat(self) -> bool:
        """
        逃离战斗（如果情况不利）
        """
        # 检查是否应该逃跑
        if self.player_hp_percent < 20:  # 血量过低时逃跑
            self.bot.logger.info("血量过低，尝试逃跑")
            
            # 按下逃跑键（通常是某个功能键）
            pyautogui.press('ESC')  # 或其他逃跑按键
            time.sleep(1.0)
            
            # 点击逃跑选项
            screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
            screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
            
            self.bot.click_position(int(screen_width * 0.5), int(screen_height * 0.6))
            return True
        
        return False