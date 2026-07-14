"""工具注册和执行系统：把工具变成可注册的插件。

核心概念:
  1. ToolRegistry —— 工具注册表：管理所有已注册的工具
  2. @register_tool  —— 装饰器：把函数变成 agent 可调用的工具
  3. ToolContext     —— 工具执行上下文：传递 memory_store、input_handler 等

加一个新工具只需三步:
    from app.tools import register_tool

    @register_tool(name="my_tool", description="...", parameters={...})
    def my_tool(inputs: dict, ctx: "ToolContext") -> str:
        # 写你的逻辑
        return "工具返回的字符串结果"

工具按功能分组（高情商私人助手的核心能力）:
  1) 时间工具    —— get_current_datetime（知道"今天是哪天"，纪念日、周末提醒等基础）
  2) 记忆工具    —— save_memory / recall_memory / list_memory / list_categories
                     / delete_memory / search_memory（长期陪伴的灵魂）
  3) 交互工具    —— ask_user（不猜、不假设，主动澄清——这本身就是高情商的体现）
"""

import datetime

from .memory import MemoryStore


# ──────────────── ToolContext：工具执行时可用的上下文 ────────────────


class ToolContext:
    """工具执行时的上下文对象。

    每个被调用的工具都会收到一个 ctx 参数，可以通过它访问:
      - ctx.memory_store   读写持久记忆
      - ctx.input_handler  向用户提问（返回用户的输入字符串）
      - ctx.task           当前任务描述（可选，供工具参考）
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        input_handler,
        task: str = "",
    ):
        self.memory_store = memory_store
        self.input_handler = input_handler
        self.task = task


# ──────────────── ToolRegistry：工具注册表 ────────────────


class ToolRegistry:
    """工具注册表。

    负责:
      1. 存储所有已注册的工具（工具定义 JSON + 执行函数）
      2. 向模型提供"工具说明书"列表（get_tool_definitions）
      3. 执行模型请求的工具调用（execute）
    """

    def __init__(self):
        # 内部存储：{工具名: {"definition": 发给模型的 JSON, "func": 执行函数}}
        self._tools: dict[str, dict] = {}

    def add(
        self,
        name: str,
        description: str,
        parameters: dict,
        required: list[str],
        func,
    ) -> None:
        """注册一个工具。"""
        self._tools[name] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required,
                    },
                },
            },
            "func": func,
        }

    def get_tool_definitions(self) -> list[dict]:
        """获取发给模型的工具定义列表。"""
        return [tool["definition"] for tool in self._tools.values()]

    def execute(self, name: str, inputs: dict, ctx: ToolContext) -> str:
        """执行一个工具，返回字符串结果。"""
        if name not in self._tools:
            return f"未知工具: '{name}'"
        try:
            return self._tools[name]["func"](inputs, ctx)
        except Exception as e:
            # 工具执行出错时，把错误信息回写给模型，让它有机会修正后重试
            return f"工具执行错误: {e}"


# ──────────────── 全局 registry + @register_tool 装饰器 ────────────────

_global_registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    parameters: dict,
    required: list[str] | None = None,
):
    """装饰器：把一个函数注册为 agent 可调用的工具。"""

    def decorator(func):
        _global_registry.add(
            name=name,
            description=description,
            parameters=parameters,
            required=required or [],
            func=func,
        )
        return func

    return decorator


def get_global_registry() -> ToolRegistry:
    """获取全局工具注册表（agent 主循环使用）。"""
    return _global_registry


# =======================================================================
# 1) 时间工具
# =======================================================================


@register_tool(
    name="get_current_datetime",
    description=(
        "Get the current date and time in human-readable format. "
        "Use this whenever you need to know what day it is, what time it is, "
        "or when planning dates, deadlines, anniversaries, or time-dependent "
        "recommendations. Returns year, month, day, weekday, and time."
    ),
    parameters={
        "timezone": {
            "type": "string",
            "description": "Optional timezone name. Defaults to local timezone. Example: 'Asia/Shanghai'.",
        }
    },
    required=[],
)
def get_current_datetime(inputs: dict, ctx: ToolContext) -> str:
    """获取当前日期和时间。"""
    now = datetime.datetime.now()
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[now.weekday()]

    return (
        f"当前时间:\n"
        f"  日期: {now.year}年{now.month}月{now.day}日\n"
        f"  星期: {weekday}\n"
        f"  时间: {now.hour:02d}:{now.minute:02d}\n"
        f"  ISO格式: {now.isoformat(timespec='seconds')}"
    )


# =======================================================================
# 2) 记忆工具（分类存储）
# =======================================================================


@register_tool(
    name="save_memory",
    description=(
        "Save a key-value pair to the agent's persistent memory, organized by category. "
        "Categories: profile (who the user is), preferences (how they like things), "
        "work (work-related), family (family members), life (personal interests), "
        "general (temporary notes and intermediate results). "
        "You can also create new categories dynamically if none of the defaults fit well."
    ),
    parameters={
        "category": {
            "type": "string",
            "description": "Memory category: profile, preferences, work, family, life, or general",
        },
        "key": {"type": "string", "description": "Identifier for this memory entry"},
        "value": {"type": "string", "description": "Data to store"},
    },
    required=["category", "key", "value"],
)
def save_memory(inputs: dict, ctx: ToolContext) -> str:
    """写入记忆（分类存储）。"""
    return ctx.memory_store.save(inputs["category"], inputs["key"], inputs["value"])


@register_tool(
    name="recall_memory",
    description="Retrieve a previously saved value from a specific memory category using its key.",
    parameters={
        "category": {
            "type": "string",
            "description": "The memory category to look in",
        },
        "key": {"type": "string", "description": "The key used when saving"},
    },
    required=["category", "key"],
)
def recall_memory(inputs: dict, ctx: ToolContext) -> str:
    """读取记忆（指定分类）。"""
    return ctx.memory_store.recall(inputs["category"], inputs["key"])


@register_tool(
    name="list_memory",
    description=(
        "List memory entries. If a category is provided, lists all keys within that category. "
        "If no category is provided, shows a summary of all categories and how many entries each has."
    ),
    parameters={
        "category": {
            "type": "string",
            "description": "Optional. The category to list. Leave empty to see a summary of all categories.",
        }
    },
    required=[],
)
def list_memory(inputs: dict, ctx: ToolContext) -> str:
    """列出记忆（指定分类或全部分类摘要）。"""
    category = inputs.get("category", "").strip()
    if category:
        return ctx.memory_store.list_category(category)
    else:
        return ctx.memory_store.list_all()


@register_tool(
    name="list_categories",
    description="List all memory categories that currently have entries. Useful for discovering what's stored before recalling.",
    parameters={},
    required=[],
)
def list_categories(inputs: dict, ctx: ToolContext) -> str:
    """列出所有有数据的分类。"""
    cats = ctx.memory_store.list_categories()
    if not cats:
        return "当前没有任何分类有数据"
    return "有数据的分类: " + ", ".join(cats)


@register_tool(
    name="delete_memory",
    description="Delete a key-value pair from a specific memory category. Use this when information is no longer needed or is outdated.",
    parameters={
        "category": {"type": "string", "description": "The memory category to delete from"},
        "key": {"type": "string", "description": "The memory key to delete"},
    },
    required=["category", "key"],
)
def delete_memory(inputs: dict, ctx: ToolContext) -> str:
    """删除记忆（指定分类）。"""
    return ctx.memory_store.delete(inputs["category"], inputs["key"])


@register_tool(
    name="search_memory",
    description=(
        "Search across all memory categories for a keyword. "
        "Matches are found in both key names and stored values (case-insensitive). "
        "Use this when you know something was saved but you're not sure which category it's in."
    ),
    parameters={
        "keyword": {
            "type": "string",
            "description": "The word or phrase to search for in memory",
        }
    },
    required=["keyword"],
)
def search_memory(inputs: dict, ctx: ToolContext) -> str:
    """跨分类搜索记忆。"""
    return ctx.memory_store.search(inputs["keyword"])


# =======================================================================
# 3) 交互工具（向用户提问）
# =======================================================================


@register_tool(
    name="ask_user",
    description=(
        "Ask the user a question and wait for their response. "
        "Use this when: 1) you need the user to make a decision, "
        "2) you need specific information that is not available from other tools, "
        "3) you need the user to confirm something, or 4) you want to offer choices. "
        "The user will type their answer and you will receive it as the tool result."
    ),
    parameters={
        "question": {
            "type": "string",
            "description": "The question to ask the user in Chinese. Be specific and clear.",
        }
    },
    required=["question"],
)
def ask_user(inputs: dict, ctx: ToolContext) -> str:
    """向用户提问，返回用户的输入。"""
    question = inputs.get("question", "请输入:")
    user_input = ctx.input_handler(question)
    return f"用户回答: {user_input}"