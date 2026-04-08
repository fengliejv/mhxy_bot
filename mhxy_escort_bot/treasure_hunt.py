import cv2
import numpy as np
import time
from typing import Optional, Tuple, List
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class TreasureHuntSystem:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        
        # 颜色阈值 (HSV格式) - 用于识别不同游戏元素
        self.color_ranges = {
            'npc': ([15, 100, 100], [25, 255, 255]),  # NPC黄色
            'dialog': ([0, 0, 200], [180, 30, 255]),   # 对话框白色
            'monster': ([0, 100, 100], [10, 255, 255]), # 怪物红色
            'treasure_map': ([100, 100, 50], [130, 255, 255]) # 藏宝图蓝色
        }
        
        # 初始化视觉大模型适配器
        try:
            from .vision_adapter import VisionModelAdapter
            # 使用提供的API密钥
            api_key = "sk-iyfyuubfvknniobmxbjylczlflucqcicqzzhrolmjqofwxog"
            self.vision_adapter = VisionModelAdapter(api_key)
            
            # 测试API密钥是否有效
            test_image = np.zeros((100, 100, 3), dtype=np.uint8)  # 创建测试图像
            test_result = self.vision_adapter.analyze_image(test_image, "这是一个测试，请返回'测试成功'")
            
            if test_result is not None:
                self.use_vision_model = True
                self.logger.info("视觉大模型适配器初始化成功")
            else:
                self.vision_adapter = None
                self.use_vision_model = False
                self.logger.warning("视觉大模型API密钥无效，将使用传统图像识别方法")
                
        except ImportError:
            self.vision_adapter = None
            self.use_vision_model = False
            self.logger.warning("无法导入视觉大模型适配器，将使用传统图像识别方法")
        except Exception as e:
            self.vision_adapter = None
            self.use_vision_model = False
            self.logger.warning(f"视觉大模型初始化失败: {str(e)}，将使用传统图像识别方法")
        
    def locate_tavern_npc(self) -> Optional[Tuple[int, int]]:
        """定位酒馆店小二"""
        screen = self.bot.capture_screen()
        if screen is None:
            self.logger.error("截图失败")
            return None
            
        # 如果启用了视觉大模型，优先使用它
        if self.use_vision_model and self.vision_adapter:
            self.logger.info("使用视觉大模型定位NPC...")
            vision_result = self.vision_adapter.detect_npc_location(screen)
            if vision_result:
                self.logger.info(f"视觉大模型检测到NPC位置: {vision_result}")
                return vision_result
        
        # 否则使用传统的颜色识别方法
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        lower, upper = self.color_ranges['npc']
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        
        # 形态学处理
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # 识别NPC位置
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            # 找到最大的轮廓（最可能是NPC）
            max_cnt = max(contours, key=cv2.contourArea)
            x,y,w,h = cv2.boundingRect(max_cnt)
            # 返回中心点坐标
            center_x = x + w // 2
            center_y = y + h // 2
            self.logger.info(f"传统方法找到NPC位置: ({center_x}, {center_y})")
            return (center_x, center_y)
        else:
            self.logger.warning("未找到NPC")
            return None

    def execute_full_hunt(self) -> bool:
        """执行完整打图流程"""
        self.logger.info("开始执行打图任务")
        
        steps = [
            ("寻找NPC", self._find_npc_and_interact),
            ("接受任务", self._accept_task),
            ("前往地点", self._navigate_to_location),
            ("挖掘宝藏", self._dig_treasure),
            ("处理战斗", self._handle_combat_if_needed),
            ("返回交任务", self._return_to_npc)
        ]
        
        for step_name, step_func in steps:
            self.logger.info(f"执行步骤: {step_name}")
            try:
                if not step_func():
                    self.logger.error(f"步骤 '{step_name}' 执行失败")
                    return False
                time.sleep(1)  # 短暂等待
            except Exception as e:
                self.logger.error(f"步骤 '{step_name}' 发生异常: {str(e)}")
                return False
                
        self.logger.info("打图任务完成！")
        return True

    def _find_npc_and_interact(self) -> bool:
        """寻找NPC并交互"""
        npc_pos = self.locate_tavern_npc()
        if not npc_pos:
            self.logger.error("未找到NPC")
            return False
            
        self.bot.click_position(*npc_pos)
        time.sleep(2)  # 等待对话框出现
        return True

    def _accept_task(self) -> bool:
        """接受任务"""
        # 点击对话框中的接受按钮
        # 这里简化处理，直接点击屏幕中央偏下的位置
        screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
        screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
        
        # 计算相对屏幕坐标
        accept_x = screen_width // 2
        accept_y = int(screen_height * 0.8)
        
        self.bot.click_position(accept_x, accept_y)
        time.sleep(2)
        return True

    def _navigate_to_location(self) -> bool:
        """前往藏宝图地点"""
        # 这里简化处理，模拟前往指定地点
        # 实际游戏中需要解析藏宝图坐标并导航
        self.logger.info("前往藏宝图地点...")
        time.sleep(3)  # 模拟移动时间
        return True

    def _dig_treasure(self) -> bool:
        """挖掘宝藏"""
        self.logger.info("挖掘宝藏...")
        # 按下使用藏宝图的快捷键（通常是Alt+3或背包中的特定位置）
        import pyautogui
        
        # 先按Alt键打开背包
        pyautogui.keyDown('alt')
        time.sleep(0.5)
        
        # 模拟点击藏宝图位置（通常在背包的第3格）
        # 计算背包中藏宝图位置的坐标
        if self.bot.screenshot_region:
            # 假设背包在屏幕下方，第3格藏宝图的位置
            bag_start_x = self.bot.screenshot_region[0] + 200  # 调整为实际坐标
            bag_start_y = self.bot.screenshot_region[1] + 800  # 调整为实际坐标
            item_slot_x = bag_start_x + (2 * 44)  # 第3格（索引2），每个格子约44px宽
            item_slot_y = bag_start_y + (0 * 44)  # 第1行
            
            # 点击藏宝图
            pyautogui.click(item_slot_x, item_slot_y)
            time.sleep(1)
            
            # 点击使用
            pyautogui.click(item_slot_x, item_slot_y)  # 再次点击确认使用
            time.sleep(2)
        
        pyautogui.keyUp('alt')
        time.sleep(3)  # 等待挖宝动画
        
        return True

    def _handle_combat_if_needed(self) -> bool:
        """如果需要，处理战斗"""
        # 检测是否进入战斗状态
        in_combat = self.bot.combat_system.detect_combat_status()
        
        # 如果传统方法检测不到，使用视觉大模型确认
        if not in_combat and self.use_vision_model and self.vision_adapter:
            screen = self.bot.capture_screen()
            if screen is not None:
                in_combat = self.vision_adapter.detect_combat_status_vision(screen)
        
        if in_combat:
            self.logger.info("检测到战斗，开始战斗处理...")
            return self.bot.combat_system.engage_combat()
        else:
            self.logger.info("未检测到战斗")
            return True

    def _return_to_npc(self) -> bool:
        """返回NPC处交任务"""
        self.logger.info("返回NPC处交任务...")
        # 重新定位NPC
        npc_pos = self.locate_tavern_npc()
        if npc_pos:
            self.bot.click_position(*npc_pos)
            time.sleep(2)
            # 点击交任务按钮
            screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
            screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
            reward_x = screen_width // 2
            reward_y = int(screen_height * 0.8)
            self.bot.click_position(reward_x, reward_y)
            time.sleep(2)
            return True
        else:
            self.logger.warning("无法找到NPC交任务")
            return False