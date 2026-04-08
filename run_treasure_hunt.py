import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mhxy_escort_bot.main import MHXYEscortBot
from mhxy_escort_bot.treasure_hunt import TreasureHuntSystem

class TreasureHuntBot(MHXYEscortBot):
    def __init__(self):
        super().__init__()
        self.treasure = TreasureHuntSystem(self)
        self.max_retries = 3

    def run_mission(self):
        """运行打图任务"""
        print("开始执行打图任务...")
        
        # 激活游戏窗口
        if not self.activate_window():
            print("无法激活游戏窗口")
            return False
            
        time.sleep(1)
        
        # 执行打图流程
        for attempt in range(self.max_retries):
            print(f"第 {attempt + 1} 次尝试...")
            try:
                if self.treasure.execute_full_hunt():
                    print("打图任务完成！")
                    return True
            except Exception as e:
                print(f"尝试 {attempt + 1} 失败: {str(e)}")
                time.sleep(3)
                
        print("所有尝试都失败了")
        return False

def main():
    bot = TreasureHuntBot()
    
    if bot.find_game_window():
        print("成功找到游戏窗口")
        bot.run_mission()
    else:
        print("未找到游戏窗口，请确保梦幻西游已启动")

if __name__ == "__main__":
    main()