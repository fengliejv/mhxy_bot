import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mhxy_escort_bot.main import MHXYEscortBot

bot = MHXYEscortBot()
if bot.find_game_window():
    bot.activate_window()
    import time
    time.sleep(1)
    screenshot = bot.capture_screen()
    if screenshot is not None:
        import cv2
        cv2.imwrite("screenshot_test.png", screenshot)
        print(f"截图已保存: screenshot_test.png, 尺寸: {screenshot.shape[1]}x{screenshot.shape[0]}")
    else:
        print("截图失败")
else:
    print("未找到游戏窗口")
