"""工具定义和执行器：告诉模型"我能做什么"，以及真正去执行它。

分为两部分:
  1. TOOLS  —— 工具定义列表（JSON Schema 格式）。发给模型看的"说明书"。
  2. execute_tool() —— 根据工具名分发到对应逻辑，返回字符串结果。

原来在 deepseek_agent.py 里:
  - tools 是一个模块级全局列表
  - execute_tool 依赖全局的 _memory 字典（通过 `global _memory` 访问）
  - 数学计算用到模块级的 _SAFE_MATH_NAMESPACE

现在改为:
  - TOOLS 仍是模块级常量（纯数据，无副作用）
  - _SAFE_MATH_NAMESPACE 是模块级常量（纯数据）
  - execute_tool 显式接收 memory_store 参数，不再依赖全局状态
"""

import math

from .memory import MemoryStore


# ──────────────── 工具定义（发给模型看的"说明书"） ────────────────

# 每个工具都是一份 JSON Schema 说明书。模型会阅读 description 字段来判断
# "这个问题是否需要调用工具"。描述写得越具体清晰，模型调用越准确。
#
# DeepSeek/OpenAI 的 tools 格式跟 Anthropic 略有不同:
#   Anthropic: 每个工具直接是 {name, description, input_schema}
#   DeepSeek/OpenAI: 每个工具是 {type: "function", function: {name, description, parameters}}
#                    外层多一层 function 包装，input_schema 改名叫 parameters
TOOLS: list[dict] = [
    {
        # 工具一：数学计算器
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate a mathematical expression and return the numeric result. "
                "Use this for any calculation: arithmetic, compound interest, percentages, etc. "
                "Example expression: '5000 * (1 + 0.07) ** 5'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A Python math expression using numbers, operators (+,-,*,/,**), and math functions (sqrt, log, etc.)",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        # 工具二：写入记忆（支持元数据：创建时间、更新时间）
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save a key-value pair to the agent's persistent working memory. "
                "Timestamps (created_at, updated_at) are recorded automatically. "
                "If the key exists, only 'value' is updated and 'updated_at' is refreshed; "
                "'created_at' is preserved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Identifier for this memory entry"},
                    "value": {"type": "string", "description": "Data to store"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        # 工具三：读取记忆（返回 value 及元数据）
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Retrieve a previously saved value from memory using its key. Returns the stored value along with its created_at and updated_at timestamps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key used when saving"}
                },
                "required": ["key"],
            },
        },
    },
    {
        # 工具四：列出所有记忆（让模型知道自己存过什么）
        "type": "function",
        "function": {
            "name": "list_memory",
            "description": "List all keys currently stored in memory, along with their created_at and updated_at timestamps. Use this to discover what information is available before trying to recall.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        # 工具五：删除记忆（清理不再需要的键）
        "type": "function",
        "function": {
            "name": "delete_memory",
            "description": "Delete a key-value pair from memory. Use this when information is no longer needed or is outdated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The memory key to delete"}
                },
                "required": ["key"],
            },
        },
    },
    {
        # 工具六：网络搜索（当前是模拟实现，未来可接入真实搜索 API）
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information, news, or data. "
                "Use this when you need up-to-date facts not in your training data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"}
                },
                "required": ["query"],
            },
        },
    },
]


# ──────────────── 数学计算安全命名空间（供 eval 使用） ────────────────

# 构建一个"安全命名空间"让 eval 只允许使用 math 模块的函数，绝不暴露 Python 内置函数。
# 如果不这样做，eval("__import__('os').system('rm -rf /')") 就会直接执行危险命令。
# 用字典推导式提取 math 模块的公开属性（即数学函数），过滤掉以下划线开头的属性（私有属性、魔术方法等）。
_SAFE_MATH_NAMESPACE: dict = {
    k: v for k, v in math.__dict__.items() if not k.startswith("_")
}
# 显式把 __builtins__ 置为空字典：切断 eval 对 print/exec/import/open 等内置的访问
_SAFE_MATH_NAMESPACE["__builtins__"] = {}


# ──────────────── 工具执行器（根据工具名分发） ────────────────

def execute_tool(
    name: str,
    inputs: dict,
    memory_store: MemoryStore,
) -> str:
    """根据工具名调用对应逻辑，把结果以字符串形式返回给智能体。

    参数:
        name:          工具名（例如 "calculate"、"save_memory"）
        inputs:        模型传给工具的参数字典（例如 {"expression": "5000 * 1.07 ** 5"}）
        memory_store:  MemoryStore 实例，供记忆类工具调用 save/recall/list/delete

    返回:
        工具执行结果字符串。如果工具名不认识，返回"未知工具"提示。
    """

    # 分支一：数学计算
    if name == "calculate":
        try:
            # 在安全命名空间里执行表达式；第二参数是 globals，第三参数 locals 省略即使用空
            result = eval(inputs["expression"], _SAFE_MATH_NAMESPACE)
            return f"{result:.4f}"
        except Exception as e:
            return f"计算错误: {e}"

    # 分支二：写入记忆
    if name == "save_memory":
        return memory_store.save(inputs["key"], inputs["value"])

    # 分支三：读取记忆
    if name == "recall_memory":
        return memory_store.recall(inputs["key"])

    # 分支四：列出所有记忆
    if name == "list_memory":
        return memory_store.list_all()

    # 分支五：删除记忆
    if name == "delete_memory":
        return memory_store.delete(inputs["key"])

    # 分支六：网络搜索（当前是模拟实现，未来可替换为真实搜索 API）
    if name == "web_search":
        # ── 生产环境 TODO：把下面这段替换为真实的搜索 API 调用 ──
        # 推荐方案:
        #   Brave Search: https://brave.com/search/api/（有免费额度）
        #   Tavily:       https://tavily.com（专为 AI 打造的搜索）
        # ────────────────────────────────────────────────────────
        return (
            f"[模拟搜索: '{inputs['query']}']\n"
            "主要结果:\n"
            "• 2025 年智能体 AI 采用率增长 340%（麦肯锡, 2026）\n"
            "• 70% 的财富 500 强公司正在试点 AI 智能体\n"
            "• LangGraph、AutoGen 和 Claude 是主流框架\n"
            "• 关键趋势: 多智能体系统正在取代传统的完整工作流"
        )

    # 兜底分支：模型返回了未定义的工具名
    return f"未知工具: '{name}'"