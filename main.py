"""入口脚本：把依赖组装起来，跑一个完整的智能体任务。

用法:
  python main.py

等价于旧版:
  python deepseek_agent.py

核心变化:
  - 旧版：所有东西都在一个文件里，依赖模块级全局变量
  - 新版：在 main() 里显式创建 client / memory_store / config，然后传给 run_agent
"""

import os
import sys

# 支持 src 布局：把 src/ 加入模块搜索路径，这样不管是 `python main.py`
# 还是 `uv run python main.py` 都能直接找到 `app` 包。
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from dotenv import load_dotenv

# 第一步：读取 .env 文件中的环境变量（放在最顶部，确保 API client 初始化前就读到）
load_dotenv()

from app import (
    AgentConfig,
    MemoryStore,
    get_client,
    run_agent,
)


def main() -> None:
    """创建所有依赖，然后跑一个示例任务。"""
    # 1. 创建 API 客户端（使用 DeepSeek API Key）
    api_client = get_client()

    # 2. 创建记忆仓库（启动时自动从 data/agent_memory.json 加载已有内容）
    memory_store = MemoryStore()

    # 3. 使用默认配置跑一个任务
    run_agent(
        # 任务描述：复利计算 + 写入记忆 + 读取记忆验证 + 搜索趋势 + 总结
        "我想用 5000 美元按 7% 的年复利投资 5 年。"
        "先计算最终金额，把结果以 'investment_result' 为键名保存到记忆，"
        "然后把它读取出来以确认保存成功，"
        "再去网络上搜索最新的智能体 AI 发展趋势，"
        "最后写一小段话，总结投资结果和你找到的关键 AI 趋势。",
        api_client,
        memory_store,
        # config=AgentConfig(max_steps=10, temperature=0.9),  # 想调参就加这行
    )


if __name__ == "__main__":
    main()