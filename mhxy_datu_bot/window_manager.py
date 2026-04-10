"""
梦幻西游打图自动化 - 游戏窗口管理模块
"""
import time
import subprocess
from typing import Optional, Tuple
import pyautogui
import pygetwindow as gw
from .config import (
    GAME_WINDOW_TITLE,
    GAME_WINDOW_CLASS,
    GAME_WINDOW_DEFAULT_WIDTH,
    GAME_WINDOW_DEFAULT_HEIGHT,
    GAME_CLIENT_PATH,
)
from .logger import setup_logger

logger = setup_logger("window_manager")


class WindowManager:
    def __init__(self):
        self.window = None
        self.window_rect = None

    def find_game_window(self) -> bool:
        windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
        if windows:
            self.window = windows[0]
            self.window_rect = (
                self.window.left,
                self.window.top,
                self.window.width,
                self.window.height,
            )
            logger.info(f"找到游戏窗口: {self.window.title}")
            return True
        logger.warning("未找到游戏窗口")
        return False

    def activate_window(self) -> bool:
        if not self.window:
            if not self.find_game_window():
                return False
        try:
            if self.window.isMinimized:
                self.window.restore()
            self.window.activate()
            time.sleep(0.5)
            logger.info("游戏窗口已激活")
            return True
        except Exception as e:
            logger.error(f"激活窗口失败: {e}")
            return False

    def launch_game(self) -> bool:
        try:
            logger.info(f"启动游戏客户端: {GAME_CLIENT_PATH}")
            subprocess.Popen(GAME_CLIENT_PATH)
            time.sleep(10)
            for _ in range(30):
                if self.find_game_window():
                    logger.info("游戏客户端启动成功")
                    return True
                time.sleep(2)
            logger.error("游戏客户端启动超时")
            return False
        except Exception as e:
            logger.error(f"启动游戏失败: {e}")
            return False

    def ensure_window_ready(self) -> bool:
        if not self.find_game_window():
            logger.info("游戏窗口未打开，尝试启动...")
            if not self.launch_game():
                return False
        if not self.activate_window():
            return False
        time.sleep(1)
        return True

    def get_window_offset(self) -> Tuple[int, int]:
        if not self.window:
            self.find_game_window()
        if self.window:
            return (self.window.left, self.window.top)
        return (0, 0)

    def game_to_screen_coords(self, game_x: int, game_y: int) -> Tuple[int, int]:
        offset_x, offset_y = self.get_window_offset()
        return (offset_x + game_x, offset_y + game_y)

    def click_game_coords(self, game_x: int, game_y: int, duration: float = 0.1) -> bool:
        screen_x, screen_y = self.game_to_screen_coords(game_x, game_y)
        try:
            pyautogui.click(screen_x, screen_y, duration=duration)
            time.sleep(0.3)
            logger.debug(f"点击游戏坐标: ({game_x}, {game_y}) -> 屏幕({screen_x}, {screen_y})")
            return True
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return False

    def move_to_coords(self, game_x: int, game_y: int) -> bool:
        screen_x, screen_y = self.game_to_screen_coords(game_x, game_y)
        try:
            pyautogui.moveTo(screen_x, screen_y, duration=0.2)
            return True
        except Exception as e:
            logger.error(f"移动鼠标失败: {e}")
            return False

    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None):
        import numpy as np
        try:
            if region:
                offset_x, offset_y = self.get_window_offset()
                screen_region = (
                    offset_x + region[0],
                    offset_y + region[1],
                    region[2],
                    region[3],
                )
                screenshot = pyautogui.screenshot(region=screen_region)
            else:
                if self.window:
                    screenshot = pyautogui.screenshot(
                        region=(
                            self.window.left,
                            self.window.top,
                            self.window.width,
                            self.window.height,
                        )
                    )
                else:
                    screenshot = pyautogui.screenshot()
            return np.array(screenshot)[:, :, ::-1].copy()
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def send_keys(self, keys: str, interval: float = 0.05) -> None:
        pyautogui.typewrite(keys, interval=interval)

    def press_hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys)
        time.sleep(0.3)
