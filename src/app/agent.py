"""智能体主循环：ReAct 模式（思考 → 行动 → 观察 → 循环直到完成）。

这是整个项目的"大脑"：
  1. 把任务描述 + 已有记忆摘要 打包成初始对话历史
  2. 循环调用模型（call_api）
  3. 模型说"我回答完了"（finish_reason == "stop"）就输出结果
  4. 模型说"我要调用工具"（finish_reason == "tool_calls"）就解析参数、执行工具、
     把工具结果追加回对话历史，继续下一轮

原来在 deepseek_agent.py 里:
  run_agent(task, config) 依赖全局的 client / _memory / tools

现在改为:
  run_agent(task, api_client, memory_store, config) → 显式接收所有依赖，无全局状态
  （cli.py 里的 main() 函数负责把这些依赖组装起来传进来）
"""

import json

from .config import AgentConfig, DEFAULT_CONFIG
from .memory import MemoryStore
from .models import call_api
from .tools import TOOLS, execute_tool


def run_agent(
    task: str,
    api_client: object,
    memory_store: MemoryStore,
    config: AgentConfig = DEFAULT_CONFIG,
) -> str:
    """执行 ReAct 智能体循环：思考（模型） → 行动（调用工具） → 观察（工具结果） → 循环直到完成。

    参数:
        task:         给智能体的自然语言任务描述。
        api_client:   OpenAI 兼容客户端实例（由 models.get_client() 创建）。
        memory_store: MemoryStore 实例，供工具读写记忆。
        config:       AgentConfig 配置对象（model_name、max_steps、temperature 等）。
                      默认使用 DEFAULT_CONFIG，如需调参:
                        run_agent(task, api_client, memory_store,
                                  config=AgentConfig(max_steps=10, temperature=0.9))

    返回:
        智能体的最终文本答复。
    """
    # 打印 60 个等号作为视觉分隔线，让输出更易读
    print(f"\n{'='*60}")
    print(f"智能体任务:\n{task}")
    print(f"{'='*60}\n")

    # ── 构造初始消息：记忆摘要（让模型知道"之前存过什么"） + 任务描述 ──
    memory_context = memory_store.to_context_text()
    messages: list[dict] = [
        {"role": "system", "content": memory_context + "\n\nTask description:\n"},
        {"role": "user", "content": task},
    ]

    # 循环计数器，配合 config.max_steps 做安全上限
    step = 0

    # ── Token 用量统计：累计每一步的输入输出 token ──
    #    prompt_tokens     → 你发给模型的部分（问题 + 对话历史）
    #    completion_tokens → 模型返回给你的部分
    #    total_tokens      → 两者之和，用来算钱
    total_prompt_tokens = 0
    total_completion_tokens = 0

    # 进入主循环：只要未达最大步数就继续
    while step < config.max_steps:
        step += 1
        print(f"--- 第 {step} 步: 思考中... ---")

        # ── 调用模型（封装后：自动带超时控制和指数退避重试） ──
        response = call_api(api_client, messages, TOOLS, config)

        # ── Token 统计：读取 API 返回的 usage 并累加 ──
        #    注意：不是所有 API 都会返回 usage，所以用 hasattr 做防御判断
        if hasattr(response, "usage") and response.usage:
            total_prompt_tokens += response.usage.prompt_tokens or 0
            total_completion_tokens += response.usage.completion_tokens or 0
            print(
                f"  [统计] 本轮: {response.usage.total_tokens} tokens "
                f"(输入 {response.usage.prompt_tokens}, 输出 {response.usage.completion_tokens})"
            )

        # 取第一条（也是唯一一条）回复消息
        response_message = response.choices[0].message

        # ── 分支 A：智能体说"我回答完了" ──────────────────────────────────────
        # DeepSeek/OpenAI 用 finish_reason 而不是 stop_reason:
        #   "stop"        → 模型认为信息已足够，给出最终答案
        #   "tool_calls"  → 模型要调用工具
        #   "length"      → 因 max_tokens 限制而截断（本项目不常见）
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "stop":
            final_text = response_message.content or "未生成任何回复。"
            print(f"\n{'='*60}")
            print(f"最终答案:\n{final_text}")
            print(f"{'='*60}")

            # ── 汇总 Token 用量和估算成本 ──
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

        # ── 分支 B：智能体说"我要调用工具" ────────────────────────────────────
        # 先把"模型本轮说的话和发起的工具调用指令"作为 assistant 消息追加回历史，
        # 让下一轮它能看到自己刚才想做什么。
        #
        # DeepSeek/OpenAI 的 assistant 消息格式:
        #   {"role": "assistant",
        #    "content": 纯文本（可能为空）,
        #    "tool_calls": 工具调用列表（每个包含 id、type、function{name, arguments}）}
        assistant_message = {
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": response_message.tool_calls,
        }
        messages.append(assistant_message)

        # 遍历模型本轮发起的所有工具调用
        tool_calls = response_message.tool_calls or []

        for tool_call in tool_calls:
            # 工具调用的唯一标识：必须原样回传，让 API 把工具结果和调用关联上
            tool_call_id = tool_call.id
            # 工具名：例如 "calculate"
            tool_name = tool_call.function.name
            # 工具参数：模型返回的是 JSON 字符串，需要用 json.loads 转成 dict
            #   例如：'{"expression": "5000 * (1 + 0.07) ** 5"}'
            #
            # ── 防御式解析：模型偶尔会返回不合法的 JSON（单引号、尾随逗号、注释等）
            #    解析失败时，不要让整个脚本崩溃，而是把错误信息回写给模型，
            #    让它"知道格式不对"，在下一轮对话中自行修正后重试
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"  ⚠️  参数解析失败: {e}")
                print(f"     模型返回的 arguments: {tool_call.function.arguments}")
                # 把错误信息作为工具结果回写给模型
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"参数解析错误: arguments 不是合法 JSON（{e}）。请检查引号、逗号等格式后重试。",
                })
                continue

            # 打印日志：本轮调用了哪个工具
            print(f"  工具: {tool_name}")
            # 打印日志：工具收到了什么参数
            print(f"  输入: {json.dumps(tool_args, ensure_ascii=False)}")

            # 真正执行工具：根据工具名走对应分支，拿到字符串结果
            result = execute_tool(tool_name, tool_args, memory_store)

            # 打印日志：工具返回了什么
            print(f"  输出: {result}\n")

            # 把工具执行结果作为 tool 消息追加回对话历史
            # DeepSeek/OpenAI 约定工具结果的消息格式:
            #   {"role": "tool",
            #    "tool_call_id": 对应工具调用的 id（必须跟上面 assistant_message 里的 id 匹配）,
            #    "content": 工具返回的字符串结果}
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })

    # 超过 max_steps 仍未结束的兜底返回
    return "已达到最大步数上限。部分结果已保存在记忆中。"