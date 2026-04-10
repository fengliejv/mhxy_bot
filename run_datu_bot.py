#!/usr/bin/env python3
"""
梦幻西游打图自动化机器人 - 运行入口
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mhxy_datu_bot import DatuBot, main

if __name__ == "__main__":
    main()
