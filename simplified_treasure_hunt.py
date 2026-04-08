import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mhxy_escort_bot.main import MHXYEscortBot
from mhxy_escort_bot.treasure_hunt import TreasureHuntSystem

class SimplifiedTreasureHunter:
    def __init__(self):
        self.bot = MHXYEscortBot()
        self.treasure = TreasureHuntSystem(self.bot)
        
    def run_single_treasure_hunt(self):
        """执行单次打图任务"""
        print("开始执行打图任务...")
        
        # 1. 激活游戏窗口
        if not self.bot.find_game_window():
            print("未找到游戏窗口！")
            return False
            
        self.bot.activate_window()
        time.sleep(1)
        
        print("步骤1: 寻找酒馆店小二...")
        # 2. 寻找NPC
        npc_pos = self.treasure.locate_tavern_npc()
        if not npc_pos:
            print("未找到NPC")
            return False
            
        print(f"找到NPC位置: {npc_pos}")
        self.bot.click_position(*npc_pos)
        time.sleep(2)
        
        print("步骤2: 接受任务...")
        # 3. 接受任务 - 简化处理，直接点击屏幕下方
        screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
        screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
        accept_x = self.bot.screenshot_region[0] + screen_width // 2
        accept_y = self.bot.screenshot_region[1] + int(screen_height * 0.8)
        self.bot.click_position(accept_x, accept_y)
        time.sleep(2)
        
        print("步骤3: 挖掘宝藏...")
        # 4. 挖掘宝藏
        success = self.treasure._dig_treasure()
        if not success:
            print("挖掘宝藏失败")
            return False
            
        time.sleep(3)  # 等待可能的战斗触发
        
        print("步骤4: 处理战斗...")
        # 5. 处理战斗
        in_combat = self.bot.combat_system.detect_combat_status()
        if in_combat:
            print("检测到战斗，开始战斗处理...")
            combat_success = self.bot.combat_system.engage_combat()
            if not combat_success:
                print("战斗处理失败，但继续执行任务")
        else:
            print("未检测到战斗")
            time.sleep(3)  # 等待一下确保没有延迟的战斗触发
        
        print("步骤5: 返回交任务...")
        # 6. 返回NPC交任务 - 简化处理
        time.sleep(2)
        self.bot.click_position(*npc_pos)  # 重新点击NPC
        time.sleep(2)
        
        # 点击交任务按钮
        reward_x = self.bot.screenshot_region[0] + screen_width // 2
        reward_y = self.bot.screenshot_region[1] + int(screen_height * 0.8)
        self.bot.click_position(reward_x, reward_y)
        time.sleep(2)
        
        print("打图任务完成！")
        return True

def main():
    hunter = SimplifiedTreasureHunter()
    success = hunter.run_single_treasure_hunt()
    
    if success:
        print("\n✅ 打图任务成功完成！")
    else:
        print("\n❌ 打图任务执行失败")

if __name__ == "__main__":
    main()