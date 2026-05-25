from typing import Any, Dict, Sequence

from .agents.tools.word_puzzle import click_word_puzzle_by_indices
from .vision import bot as vision_bot


def solve_word_puzzle_stub(answer_indices: Sequence[int]) -> Dict[str, Any]:
    result = click_word_puzzle_by_indices(answer_indices)

    try:
        vision_bot.tap_template("assets/android/xiaorenwu/confirm.png")
        result["confirm_tapped"] = True
    except Exception as e:
        result["confirm_tapped"] = False
        result["confirm_error"] = str(e)

    return result
