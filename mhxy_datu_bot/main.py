"""
梦幻西游打图自动化 - 主控制器模块
整合所有模块，实现完整的打图自动化流程
"""

import time
import signal
import sys
from typing import Dict, Optional
from .config import (
    MAX_DAILY_TASKS,
    SANJIE_MIN_THRESHOLD,
    SANJIE_FREE_TASKS,
    SANJIE_COST_PER_TASK,
)
from .logger import setup_logger
from .window_manager import WindowManager
from .image_recognition import ImageRecognition
from .character_status import CharacterStatus
from .inventory_manager import InventoryManager
from .navigation_system import NavigationSystem
from .combat_system import CombatSystem
from .npc_interaction import NPCInteraction
from .datu_task import DatuTask

logger = setup_logger("main_controller")


class DatuBot:
    def __init__(self):
        self.running = False
        self.paused = False
        self.task_count = 0
        self.max_tasks = MAX_DAILY_TASKS
        
        self.window_manager = WindowManager()
        self.image_recognition = ImageRecognition()
        
        self.character_status = CharacterStatus(self.window_manager, self.image_recognition)
        self.inventory_manager = InventoryManager(self.window_manager, self.image_recognition)
        self.navigation = NavigationSystem(self.window_manager, self.image_recognition)
        self.npc_interaction = NPCInteraction(self.window_manager, self.image_recognition)
        self.combat = CombatSystem(self.window_manager, self.image_recognition, self.character_status)
        self.datu_task = DatuTask(
            self.window_manager, 
            self.image_recognition, 
            self.navigation, 
            self.combat, 
            self.npc_interaction
        )
        
        self._setup_signal_handlers()
        
        logger.info("打图机器人初始化完成")

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"收到信号 {signum}，停止运行")
        self.stop()
        sys.exit(0)

    def initialize(self) -> bool:
        logger.info("=" * 50)
        logger.info("开始初始化检查")
        logger.info("=" * 50)
        
        logger.info("[1/5] 检查游戏窗口...")
        if not self._check_game_window():
            logger.error("游戏窗口检查失败")
            return False
        logger.info("✓ 游戏窗口检查通过")
        
        logger.info("[2/5] 检查角色状态...")
        if not self._check_character_status():
            logger.error("角色状态检查失败")
            return False
        logger.info("✓ 角色状态检查通过")
        
        logger.info("[3/5] 检查背包空间...")
        if not self._check_inventory():
            logger.error("背包检查失败")
            return False
        logger.info("✓ 背包检查通过")
        
        logger.info("[4/5] 检查必备物品...")
        if not self._check_essential_items():
            logger.error("必备物品检查失败")
            return False
        logger.info("✓ 必备物品检查通过")
        
        logger.info("[5/5] 检查三界功绩...")
        if not self._check_sanjie_points():
            logger.error("三界功绩检查失败")
            return False
        logger.info("✓ 三界功绩检查通过")
        
        logger.info("=" * 50)
        logger.info("✅ 初始化完成，进入主循环")
        logger.info("=" * 50)
        
        return True

    def _check_game_window(self) -> bool:
        if not self.window_manager.find_game_window():
            logger.info("游戏窗口未打开，尝试启动游戏...")
            if not self.window_manager.launch_game():
                logger.error("无法启动游戏")
                return False
        
        if not self.window_manager.activate_window():
            logger.error("无法激活游戏窗口")
            return False
        
        time.sleep(1.0)
        return True

    def _check_character_status(self) -> bool:
        status = self.character_status.full_status_check()
        
        if status["needs_recovery"]:
            logger.info(f"角色状态需要恢复: {status['issues']}")
            if not self.character_status.recover_all():
                logger.warning("状态恢复未完全成功，但继续执行")
        
        return True

    def _check_inventory(self) -> bool:
        inventory_check = self.inventory_manager.full_inventory_check()
        
        if inventory_check["needs_action"]:
            logger.info(f"背包需要处理: {inventory_check['actions']}")
            if not self.inventory_manager.handle_inventory_issues():
                logger.warning("背包问题处理未完全成功，但继续执行")
        
        return True

    def _check_essential_items(self) -> bool:
        items_status = self.inventory_manager.check_essential_items()
        
        all_sufficient = True
        for item_name, status in items_status.items():
            if not status["sufficient"]:
                logger.warning(f"{item_name} 不足: 当前 {status['count']}, 需要 {status['min_count']}")
                needed = status["min_count"] - status["count"]
                if not self.inventory_manager.purchase_items(item_name, needed):
                    logger.error(f"无法购买 {item_name}")
                    all_sufficient = False
        
        return all_sufficient

    def _check_sanjie_points(self) -> bool:
        points = self.datu_task.check_sanjie_points()
        
        if points < SANJIE_MIN_THRESHOLD:
            logger.error(f"三界功绩不足: 当前 {points}, 最低需要 {SANJIE_MIN_THRESHOLD}")
            return False
        
        logger.info(f"三界功绩: {points}")
        return True

    def run(self, max_tasks: int = None):
        if max_tasks:
            self.max_tasks = max_tasks
        
        logger.info(f"开始运行打图机器人，最大任务数: {self.max_tasks}")
        
        if not self.initialize():
            logger.error("初始化失败，无法启动")
            return False
        
        self.running = True
        
        try:
            while self.running and self.task_count < self.max_tasks:
                if self.paused:
                    time.sleep(1.0)
                    continue
                
                logger.info(f"\n{'='*50}")
                logger.info(f"开始第 {self.task_count + 1} 次打图任务")
                logger.info(f"{'='*50}")
                
                if not self._pre_task_check():
                    logger.error("任务前检查失败，停止运行")
                    break
                
                success = self._execute_task_cycle()
                
                if success:
                    self.task_count += 1
                    logger.info(f"✓ 任务完成，已完成 {self.task_count} 次")
                else:
                    logger.warning("✗ 任务失败")
                
                self._post_task_maintenance()
                
                if self.task_count < self.max_tasks:
                    wait_time = 2.0
                    logger.info(f"等待 {wait_time} 秒后继续...")
                    time.sleep(wait_time)
        
        except Exception as e:
            logger.error(f"运行出错: {e}")
            return False
        
        finally:
            self._print_statistics()
        
        logger.info("打图机器人运行结束")
        return True

    def _pre_task_check(self) -> bool:
        if not self.datu_task.is_sanjie_sufficient():
            logger.error("三界功绩不足，无法继续")
            return False
        
        status = self.character_status.detect_hp_mp()
        if status["hp"] < 30 or status["mp"] < 20:
            logger.info("状态不佳，进行恢复...")
            self.character_status.recover_all()
        
        space = self.inventory_manager.detect_inventory_space()
        if space["free"] < 2:
            logger.info("背包空间不足，进行整理...")
            self.inventory_manager.organize_inventory()
            space = self.inventory_manager.detect_inventory_space()
            if space["free"] < 2:
                logger.warning("背包空间仍然不足，尝试存储...")
                self.inventory_manager.store_items_to_warehouse()
        
        return True

    def _execute_task_cycle(self) -> bool:
        return self.datu_task.execute_single_task()

    def _post_task_maintenance(self) -> None:
        logger.info("任务后维护...")
        
        status = self.character_status.detect_hp_mp()
        if status["hp"] < 60:
            self.character_status.recover_hp()
        if status["mp"] < 40:
            self.character_status.recover_mp()
        
        if self.task_count % 10 == 0:
            logger.info("每10次任务检查一次背包...")
            self.inventory_manager.detect_inventory_space()

    def _print_statistics(self) -> None:
        stats = self.datu_task.get_statistics()
        
        logger.info("\n" + "=" * 50)
        logger.info("打图统计报告")
        logger.info("=" * 50)
        logger.info(f"总任务数: {stats['total_tasks']}")
        logger.info(f"成功次数: {stats['success_count']}")
        logger.info(f"失败次数: {stats['fail_count']}")
        logger.info(f"成功率: {stats['success_rate']:.1f}%")
        logger.info(f"剩余三界功绩: {stats['sanjie_points']}")
        logger.info("=" * 50)

    def pause(self):
        logger.info("暂停打图机器人")
        self.paused = True

    def resume(self):
        logger.info("恢复打图机器人")
        self.paused = False

    def stop(self):
        logger.info("停止打图机器人")
        self.running = False

    def get_status(self) -> Dict:
        return {
            "running": self.running,
            "paused": self.paused,
            "task_count": self.task_count,
            "max_tasks": self.max_tasks,
            "current_hp": self.character_status.hp_percent,
            "current_mp": self.character_status.mp_percent,
            "inventory_space": self.inventory_manager.free_slots,
            "sanjie_points": self.datu_task.sanjie_points,
        }


def main():
    print("=" * 50)
    print("梦幻西游打图自动化机器人")
    print("=" * 50)
    
    bot = DatuBot()
    
    try:
        bot.run(max_tasks=MAX_DAILY_TASKS)
    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
        bot.stop()
    
    print("程序结束")


if __name__ == "__main__":
    main()
