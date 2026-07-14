"""入口脚本：把依赖组装起来，跑一个完整的智能体任务。

支持三种方式指定任务:
  1. 命令行参数: python main.py "你好，今天是几年几月几日，星期几？"
  2. 交互式输入:  python main.py（然后按提示输入）
  3. 使用示例:    直接回车使用内置示例任务

核心变化（相比把任务写死在代码里的旧版）:
  - 任务描述可动态输入，不用改代码
  - agent 可以调用 ask_user 工具，在运行中向用户提问
  - 不再依赖任何写死在代码里的任务字符串
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

# 示例任务：当用户没有输入任何任务描述时，使用这个作为默认示例。
# （仍写在代码里，但只作为"首次使用的演示内容"，不是唯一可跑的任务）
_DEFAULT_TASK = "你好，今天是几年几月几日，星期几？"


def _get_task_from_args_or_interactive() -> str:
    """获取任务描述：优先命令行参数，其次交互式输入，最后用示例。"""
    # 方式 1：命令行参数 —— python main.py "任务描述"
    if len(sys.argv) > 1:
        return sys.argv[1]

    # 方式 2：交互式输入 —— 让用户在启动时输入任务
    print("=" * 60)
    print("请输入你想让智能体帮你做的事情")
    print("（直接回车使用内置示例任务，输入 q 退出）")
    print("=" * 60)
    user_input = input("任务描述: ").strip()

    if user_input.lower() in ("q", "quit", "exit"):
        print("已取消。")
        sys.exit(0)

    if user_input:
        return user_input

    # 方式 3：使用默认示例任务
    print(f"\n（使用示例任务）\n")
    return _DEFAULT_TASK


def main() -> None:
    """创建所有依赖，获取任务描述，然后跑 agent。"""
    # 1. 获取任务描述（命令行参数 / 交互式 / 默认示例）
    task = _get_task_from_args_or_interactive()

    # 2. 创建 API 客户端（使用 DeepSeek API Key）
    api_client = get_client()

    # 3. 创建记忆仓库（启动时自动从 data/agent_memory.json 加载已有内容）
    memory_store = MemoryStore()

    # 4. 启动 agent 主循环（传入 None 表示使用全局 registry 和默认输入处理）
    #    如果想自定义工具，创建一个 ToolRegistry 实例传进来即可。
    run_agent(
        task,
        api_client,
        memory_store,
        # config=AgentConfig(max_steps=10, temperature=0.9),  # 想调参就加这行
        # registry=my_custom_registry,                        # 测试时替换工具
        # input_handler=my_custom_input_handler,              # GUI 场景替换输入方式
    )


if __name__ == "__main__":
    main()