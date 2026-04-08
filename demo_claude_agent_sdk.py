import os
from pathlib import Path

import anyio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("未检测到 ANTHROPIC_API_KEY。你可以先设置：")
        print('  export ANTHROPIC_API_KEY="YOUR_KEY_HERE"')
        print("如果你本机已登录 Claude Code，某些环境下也可能无需显式设置该变量。")
        print("但在受限沙箱环境下可能无法读取本机 Claude Code 的凭据文件，因此这里直接退出。")
        return

    prompt = os.environ.get(
        "CLAUDE_DEMO_PROMPT",
        "列出当前目录下的文件，并用 3 条要点总结这里像是什么项目。",
    )

    options = ClaudeAgentOptions(
        cwd=Path.cwd(),
        allowed_tools=["Glob", "Read", "Grep"],
        permission_mode="default",
        max_turns=2,
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="")


if __name__ == "__main__":
    anyio.run(main)
