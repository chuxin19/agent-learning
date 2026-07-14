"""智能体主循环：ai 模式（思考 → 行动 → 观察 → 循环直到完成）。

核心变化（相比旧版）:
  - 从 prompts/system.txt 读取 system prompt，不再硬编码在 Python 里
  - 从 ToolRegistry 动态读取工具列表（ToolRegistry 插件化）
  - 通过 ToolContext 传递 memory_store 和 input_handler，支持动态交互
  - 新增时间工具 get_current_datetime，agent 可获取真实时间
"""

import json
import os

from .config import AgentConfig, DEFAULT_CONFIG
from .memory import MemoryStore
from .models import call_api
from .tools import ToolRegistry, ToolContext, get_global_registry


# ──────────────── 提示词文件加载 ────────────────


def load_prompt_file(filename: str) -> str:
    """从 prompts/ 目录加载提示词文件，返回字符串内容。

    使用 __file__ 定位 prompts 目录，这样不管从哪个目录运行脚本都能找到。
    文件不存在时返回空字符串（调用方需要处理 fallback 逻辑）。
    """
    prompts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
    filepath = os.path.join(prompts_dir, filename)

    # 也尝试项目根目录下的 prompts/（兼容开发时在项目根目录运行的场景）
    project_root_prompts = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts",
        filename,
    )

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    elif os.path.exists(project_root_prompts):
        with open(project_root_prompts, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _build_system_message(memory_store: MemoryStore) -> str:
    """构建 system message：从 system.txt 读取身份设定 + 记忆上下文。"""
    system_prompt = load_prompt_file("system.txt")

    # Fallback：如果 system.txt 不存在，用一个简短的默认提示词
    if not system_prompt:
        system_prompt = (
            "You are a warm, emotionally intelligent personal assistant. "
            "Your value is in people —— remembering who they are and caring about what they care about. "
            "Think carefully before responding. Consider their situation and feelings. "
            "Use Chinese unless asked otherwise. "
            "Use your memory tools often: save_memory, recall_memory, list_memory, search_memory. "
            "Never invent facts. If unsure, ask_user."
        )

    memory_context = memory_store.to_context_text()

    # 身份设定 + 记忆上下文，让模型知道它是谁 + 之前存了什么
    return f"{system_prompt}\n\n{memory_context}\n"


# ──────────────── 默认输入处理 ────────────────


def default_input_handler(prompt: str) -> str:
    """默认的用户输入处理：命令行 prompt + input()。"""
    print(f"\n🤖 Agent 问: {prompt}")
    try:
        return input("你的回答: ")
    except EOFError:
        return "(用户未输入)"


# ──────────────── 主循环 ────────────────


def run_agent(
    task: str,
    api_client: object,
    memory_store: MemoryStore,
    config: AgentConfig = DEFAULT_CONFIG,
    registry: ToolRegistry | None = None,
    input_handler=None,
) -> str:
    """执行 ai 智能体循环：思考（模型） → 行动（调用工具） → 观察（工具结果） → 循环直到完成。

    参数:
        task:          给智能体的自然语言任务描述。
        api_client:    OpenAI 兼容客户端实例（由 models.get_client() 创建）。
        memory_store:  MemoryStore 实例，供工具读写记忆。
        config:        AgentConfig 配置对象。
        registry:      ToolRegistry 实例。默认使用全局 registry。
        input_handler: 用户输入处理函数。签名: def handler(prompt: str) -> str
    """
    if registry is None:
        registry = get_global_registry()
    if input_handler is None:
        input_handler = default_input_handler

    # 构造工具执行上下文：供 memory 工具读写、供 ask_user 工具提问
    tool_ctx = ToolContext(
        memory_store=memory_store,
        input_handler=input_handler,
        task=task,
    )

    # ── 用户输入自动记录：先存下来，再交给模型处理
    #    不再依赖模型"自觉"调用 save_memory，保证用户说过的话一定会被记录
    auto_save_result = memory_store.save_user_input(task)
    if auto_save_result:
        print(f"  💾  {auto_save_result}")

    # 打印分隔线
    print(f"\n{'='*60}")
    print(f"智能体任务:\n{task}")
    print(f"{'='*60}\n")

    # ── 从文件读取 system prompt + 记忆上下文 构造初始消息 ──
    system_content = _build_system_message(memory_store)
    messages: list[dict] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": task},
    ]

    step = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    while step < config.max_steps:
        step += 1
        print(f"--- 第 {step} 步: 思考中... ---")

        # 从 registry 动态读取工具定义
        response = call_api(api_client, messages, registry.get_tool_definitions(), config)

        # Token 统计
        if hasattr(response, "usage") and response.usage:
            total_prompt_tokens += response.usage.prompt_tokens or 0
            total_completion_tokens += response.usage.completion_tokens or 0
            print(
                f"  [统计] 本轮: {response.usage.total_tokens} tokens "
                f"(输入 {response.usage.prompt_tokens}, 输出 {response.usage.completion_tokens})"
            )

        response_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # ── 分支 A：智能体说"我回答完了" ──
        if finish_reason == "stop":
            final_text = response_message.content or "未生成任何回复。"
            print(f"\n{'='*60}")
            print(f"最终答案:\n{final_text}")
            print(f"{'='*60}")

            total_tokens = total_prompt_tokens + total_completion_tokens
            if total_tokens > 0:
                cost_input = total_prompt_tokens * config.cost_input_per_million / 1_000_000
                cost_output = total_completion_tokens * config.cost_output_per_million / 1_000_000
                cost_total = cost_input + cost_output
                print(f"\n💡 Token 统计（共 {step} 步）：")
                print(f"   输入: {total_prompt_tokens} tokens")
                print(f"   输出: {total_completion_tokens} tokens")
                print(f"   总计: {total_tokens} tokens")
                print(f"   估算费用: ${cost_total:.4f} (约 {cost_total * 7.2:.2f} 元人民币)")
                print(f"{'='*60}\n")

            return final_text

        # ── 分支 B：智能体说"我要调用工具" ──
        assistant_message = {
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": response_message.tool_calls,
        }
        messages.append(assistant_message)

        tool_calls = response_message.tool_calls or []

        for tool_call in tool_calls:
            tool_call_id = tool_call.id
            tool_name = tool_call.function.name

            # 解析参数（防御式：模型偶尔返回不合法的 JSON）
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"  ⚠️  参数解析失败: {e}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"参数解析错误: arguments 不是合法 JSON（{e}）。请检查引号、逗号等格式后重试。",
                })
                continue

            print(f"  工具: {tool_name}")
            print(f"  输入: {json.dumps(tool_args, ensure_ascii=False)}")

            # 从 registry 动态查找并执行
            result = registry.execute(tool_name, tool_args, tool_ctx)

            print(f"  输出: {result}\n")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })

    return "已达到最大步数上限。部分结果已保存在记忆中。"