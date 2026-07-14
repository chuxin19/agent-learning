"""命令行入口：组装依赖并运行智能体任务。

这是 `pyproject.toml` 中 `run-agent` 脚本的入口函数。
使用方式:
  方式一（推荐）: python main.py
  方式二（安装后）: run-agent
"""

from dotenv import load_dotenv

# 先读取 .env 文件（放在最顶部，确保 API client 初始化前就读到）
load_dotenv()

from .agent import run_agent
from .config import AgentConfig
from .memory import MemoryStore
from .models import get_client


DEFAULT_TASK = "你好，今天是几年几月几日，星期几？"


def main() -> None:
    """创建所有依赖，然后跑一个示例任务。"""
    api_client = get_client()
    memory_store = MemoryStore()

    run_agent(
        DEFAULT_TASK,
        api_client,
        memory_store,
        # config=AgentConfig(max_steps=10, temperature=0.9),  # 想调参就取消注释
    )


if __name__ == "__main__":
    main()