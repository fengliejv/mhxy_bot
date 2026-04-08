import os
from typing import Literal
from pathlib import Path

from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_community.chat_models.tongyi import ChatTongyi

def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(Path(__file__).resolve().parent / ".env")

tavily_api_key = os.environ.get("TAVILY_API_KEY")
if not tavily_api_key:
    raise RuntimeError("Missing required environment variable: TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_api_key)

dashscope_api_key = os.environ.get("DASHSCOPE_API_KEY")
if not dashscope_api_key:
    raise RuntimeError("Missing required environment variable: DASHSCOPE_API_KEY")

dashscope_api_base = os.environ.get("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
import dashscope

dashscope.base_http_api_url = dashscope_api_base

tongyi_model = os.environ.get("TONGYI_MODEL", "qwen-plus").strip()
if tongyi_model.startswith("qwen3") and tongyi_model.endswith("-plus"):
    tongyi_model = "qwen-plus"
elif tongyi_model.startswith("qwen3") and tongyi_model.endswith("-max"):
    tongyi_model = "qwen-max"
elif tongyi_model.startswith("qwen3") and tongyi_model.endswith("-turbo"):
    tongyi_model = "qwen-turbo"

supported_models = {"qwen-turbo", "qwen-plus", "qwen-max", "qwen-long"}
if tongyi_model not in supported_models:
    print(f"Warning: Unsupported TONGYI_MODEL={tongyi_model!r}; falling back to 'qwen-plus'.")
    tongyi_model = "qwen-plus"

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


# System prompt to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Your job is to conduct thorough research and then write a polished report.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of results to return, the topic, and whether raw content should be included.
"""

agent = create_deep_agent(
    model=ChatTongyi(
        model=tongyi_model,
        api_key=dashscope_api_key,
    ),
    tools=[internet_search],
    system_prompt=research_instructions,
)

result = agent.invoke({"messages": [{"role": "user", "content": "What is langgraph?"}]})

# Print the agent's response
print(result["messages"][-1].content)
