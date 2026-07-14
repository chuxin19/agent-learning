#!/usr/bin/env python3
# shebang：让脚本可在类 Unix 系统下用 ./deepseek_agent.py 直接执行

"""
模块级文档字符串：整体说明本文件的用途、依赖、配置方式
智能体 AI 入门示例 — 基于 DeepSeek API（兼容 OpenAI 协议）构建 ReAct 智能体

依赖安装（见项目根目录 requirements.txt）：
  pip install -r requirements.txt

API Key 配置：
  方法 1（推荐）：把 key 放在项目根目录的 .env 文件里
    DEEPSEEK_API_KEY=你的真实key
    （代码里用 python-dotenv 自动读取）

  方法 2：临时设置环境变量
    export DEEPSEEK_API_KEY=你的真实key   # Mac / Linux 系统
    $env:DEEPSEEK_API_KEY = "你的真实key"  # Windows PowerShell

DeepSeek 平台：https://platform.deepseek.com
API 文档：https://api-docs.deepseek.com
"""

# ——— 读取 .env 文件中的环境变量（放在最顶部，确保 API client 初始化前就读到） ———
# 从 python-dotenv 包导入 load_dotenv 函数
from dotenv import load_dotenv
# 执行 load_dotenv：它会自动在当前目录找 .env 文件，把里面的 KEY=VALUE 写入 os.environ
# 这样后面创建 OpenAI 客户端时，os.getenv("DEEPSEEK_API_KEY") 就能读到值
load_dotenv()

# 导入 os 模块：用于调用 os.getenv() 读取环境变量中的 API Key
import os
# 导入 OpenAI 官方 SDK — DeepSeek API 兼容 OpenAI 协议，所以可以直接用它
from openai import OpenAI
# 导入 JSON 模块：用于把工具参数字典转成可读字符串打印输出
import json
# 导入数学模块：供计算工具使用（例如 sqrt、log、sin、cos 等）
import math


# ─── 第 0 步：初始化 API 客户端 ──────────────────────────────────────────────

# 创建一个 OpenAI 客户端实例，但把 base_url 指向 DeepSeek 的 API 服务器
# 这就是"兼容 OpenAI 协议"的含义：客户端库是 OpenAI 官方的，只是改一下请求地址
# api_key 从环境变量 DEEPSEEK_API_KEY 中读取（由上面 load_dotenv 加载的 .env 文件提供）
client = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY")
)


# ─── 第 1 步：定义工具（告诉模型"我能做什么"） ─────────────────────────────────
# 每个工具都是一份 JSON Schema 说明书。模型会阅读 description 字段来判断
# "这个问题是否需要调用工具"。描述写得越具体清晰，模型调用越准确。
# 注意：下面的 description 是发给模型看的提示内容，用英文模型识别效果更好
#
# DeepSeek/OpenAI 的 tools 格式跟 Anthropic 略有不同：
#   Anthropic: 每个工具直接是 {name, description, input_schema}
#   DeepSeek/OpenAI: 每个工具是 {type: "function", function: {name, description, parameters}}
#                    外层多一层 function 包装，input_schema 改名叫 parameters

# 工具清单：一个列表，每个元素是一个工具的完整 JSON Schema 定义
tools = [
    {
        # DeepSeek/OpenAI 要求每个工具声明类型为 "function"
        "type": "function",
        "function": {
            # 工具一：数学计算器
            # 工具名：模型返回的 tool_calls 里会原样引用这个字符串
            "name": "calculate",
            # 工具用途描述：这是给模型看的关键文字，它据此决定"此时是否该调用这个工具"
            "description": (
                "Evaluate a mathematical expression and return the numeric result. "
                "Use this for any calculation: arithmetic, compound interest, percentages, etc. "
                "Example expression: '5000 * (1 + 0.07) ** 5'"
            ),
            # 参数约束：告诉模型传入参数必须符合的 JSON Schema 结构
            # 在 DeepSeek/OpenAI 协议里这个字段叫 parameters（跟 Anthropic 的 input_schema 同含义）
            "parameters": {
                "type": "object",
                "properties": {
                    # 参数字段 expression：必须是字符串
                    "expression": {
                        "type": "string",
                        "description": "A Python math expression using numbers, operators (+,-,*,/,**), and math functions (sqrt, log, etc.)"
                    }
                },
                # expression 是必填字段，缺失会被拒绝
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            # 工具二：写入记忆
            "name": "save_memory",
            "description": "Save a key-value pair to the agent's working memory for use in later steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key":   {"type": "string", "description": "Identifier for this memory entry"},
                    "value": {"type": "string", "description": "Data to store"}
                },
                # key 和 value 都必填
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            # 工具三：读取记忆
            "name": "recall_memory",
            "description": "Retrieve a previously saved value from memory using its key.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key used when saving"}
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            # 工具四：网络搜索
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
                "required": ["query"]
            }
        }
    }
]


# ─── 第 2 步：实现工具的真实逻辑（让模型说的"指令"真正做事） ─────────────────────

# 模块级全局字典：用作智能体的"短期记忆"，键值对在多轮之间保持
# 声明类型 dict[str, str] 并初始化为空字典
_memory: dict[str, str] = {}

# 构建一个"安全命名空间"让 eval 只允许使用 math 模块的函数，绝不暴露 Python 内置函数
# 如果不这样做，eval("__import__('os').system('rm -rf /')") 就会直接执行危险命令
# 用字典推导式提取 math 模块的公开属性（即数学函数）
# 过滤掉以下划线开头的属性（私有属性、魔术方法等）
_SAFE_MATH_NAMESPACE = {
    k: v for k, v in math.__dict__.items() if not k.startswith("_")
}
# 显式把 __builtins__ 置为空字典：切断 eval 对 print/exec/import/open 等内置的访问
_SAFE_MATH_NAMESPACE["__builtins__"] = {}


# 工具执行函数：传入工具名 + 模型给的参数字典，返回字符串结果
def execute_tool(name: str, inputs: dict) -> str:
    """根据工具名调用对应逻辑，把结果以字符串形式返回给智能体。"""

    # 分支一：数学计算
    if name == "calculate":
        try:
            # 在安全命名空间里执行表达式；第二参数是 globals，第三参数 locals 省略即使用空
            result = eval(inputs["expression"], _SAFE_MATH_NAMESPACE)
            # 把数值结果格式化为保留 4 位小数的字符串
            return f"{result:.4f}"
        # 捕获所有异常（语法错误、除零、函数名不存在等）
        except Exception as e:
            # 把异常信息转成中文提示返回给模型，让它知道失败原因
            return f"计算错误: {e}"

    # 分支二：写入记忆
    elif name == "save_memory":
        # 直接向全局字典 _memory 写入键值对
        _memory[inputs["key"]] = inputs["value"]
        # 返回确认文字，让模型在下一轮能看到"保存成功"
        return f"已保存 '{inputs['key']}' = '{inputs['value']}'"

    # 分支三：读取记忆
    elif name == "recall_memory":
        # 用字典 get 取值，找不到返回 None
        value = _memory.get(inputs["key"])
        # 找到就返回值字符串，否则返回中文提示
        return value if value else f"未找到记忆项 '{inputs['key']}'"

    # 分支四：网络搜索（当前是模拟实现）
    elif name == "web_search":
        # 生产环境：把下面这段替换为真实的搜索 API 调用
        # 推荐方案：
        #   Brave Search: https://brave.com/search/api/（有免费额度）
        #   Tavily:       https://tavily.com（专为 AI 打造的搜索）
        # 使用 Brave 的示例代码：
        #   import requests
        #   r = requests.get("https://api.search.brave.com/res/v1/web/search",
        #       params={"q": inputs["query"]}, headers={"X-Subscription-Token": BRAVE_API_KEY})
        #   return r.json()["web"]["results"][0]["description"]
        # ───────────────────────────────────────────────────────────────
        # 返回一段写死的模拟搜索结果，方便不配置额外 API 也能跑通全流程
        return (
            f"[模拟搜索: '{inputs['query']}']\n"
            "主要结果:\n"
            "• 2025 年智能体 AI 采用率增长 340%（麦肯锡, 2026）\n"
            "• 70% 的财富 500 强公司正在试点 AI 智能体\n"
            "• LangGraph、AutoGen 和 Claude 是主流框架\n"
            "• 关键趋势: 多智能体系统正在取代传统的完整工作流"
        )

    # 兜底分支：模型返回了未在此文件中定义的工具名
    return f"未知工具: '{name}'"


# ─── 第 3 步：智能体主循环（ReAct 模式：思考 → 行动 → 观察，循环直到完成） ───────────

# 智能体主函数：传入自然语言任务，最多循环 max_steps 轮，返回最终答复文本
def run_agent(task: str, max_steps: int = 15) -> str:
    """
    执行 ReAct 智能体循环：
      思考（模型） → 行动（调用工具） → 观察（工具结果） → 循环直到完成。

    参数:
        task:      给智能体的自然语言任务描述。
        max_steps: 安全上限，防止智能体陷入无限循环。

    返回:
        智能体的最终文本答复。
    """
    # 打印 60 个等号作为视觉分隔线，让输出更易读
    print(f"\n{'='*60}")
    # 打印本次交给智能体的任务描述
    print(f"智能体任务:\n{task}")
    # 再打一条分隔线
    print(f"{'='*60}\n")

    # 对话历史列表：DeepSeek/OpenAI API 规定的消息结构；初始只有用户的任务这一条
    messages = [{"role": "user", "content": task}]
    # 循环计数器，配合 max_steps 做安全上限
    step = 0

    # 进入主循环：只要未达最大步数就继续
    while step < max_steps:
        # 先自增，从 Step 1 开始打印
        step += 1
        # 打印日志，让终端可以看到当前进行到哪一步
        print(f"--- 第 {step} 步: 思考中... ---")

        # ─────────────────────────────────────────────────────────
        # 关键差异：DeepSeek/OpenAI 的 API 调用方式
        # Anthropic: client.messages.create(model=..., tools=..., messages=...)
        # DeepSeek/OpenAI: client.chat.completions.create(model=..., tools=..., tool_choice=..., messages=...)
        #   多出一个 tool_choice 参数，用 "auto" 让模型自己决定要不要调用工具
        # ─────────────────────────────────────────────────────────
        response = client.chat.completions.create(
            # 使用 DeepSeek 的对话模型（支持 tool calling）
            model="deepseek-chat",
            # 限制单次回复最多 1024 token，防止啰嗦或陷入长篇
            max_tokens=1024,
            # 把工具清单（JSON Schema）一起传过去；模型据此"知道"自己能调用哪些工具
            tools=tools,
            # "auto" 让模型自己决定：是直接回答还是调工具
            tool_choice="auto",
            # 完整对话历史：模型能看到自己之前每一步说的话、工具返回的结果
            messages=messages
        )

        # 取第一条（也是唯一一条）回复消息
        # Anthropic 的 response 直接就有 .content 和 .stop_reason
        # DeepSeek/OpenAI 的 response 结构是 response.choices[0].message
        response_message = response.choices[0].message

        # ── 分支 A：智能体说"我回答完了" ──────────────────────────────────────
        # DeepSeek/OpenAI 用 finish_reason 而不是 stop_reason
        #   "stop"        → 模型认为信息已足够，给出最终答案
        #   "tool_calls"  → 模型要调用工具
        #   "length"      → 因 max_tokens 限制而截断（本项目不常见）
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "stop":
            # 直接取模型返回的文本内容
            final_text = response_message.content or "未生成任何回复。"
            print(f"\n{'='*60}")
            # 把最终答案打印到终端
            print(f"最终答案:\n{final_text}")
            print(f"{'='*60}\n")
            # 返回最终文本，函数结束，while 循环终止
            return final_text

        # ── 分支 B：智能体说"我要调用工具" ────────────────────────────────────
        # 先把"模型本轮说的话和发起的工具调用指令"作为 assistant 消息追加回历史，让下一轮它能看到自己刚才想做什么
        #
        # 注意：DeepSeek/OpenAI 的 assistant 消息结构跟 Anthropic 不同
        #   Anthropic: {"role": "assistant", "content": 内容块列表}
        #   DeepSeek/OpenAI: {"role": "assistant",
        #                     "content": 纯文本（可能为 null）,
        #                     "tool_calls": 工具调用列表（每个包含 id、function.name、function.arguments）}
        assistant_message = {
            "role": "assistant",
            "content": response_message.content or "",  # 模型说的话（可能为空）
            # tool_calls 是 DeepSeek/OpenAI 的必填字段，需要原样传回给模型
            # 每一个 tool_call 对象包含 id、type、function{name, arguments}
            "tool_calls": response_message.tool_calls
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
            tool_args = json.loads(tool_call.function.arguments)

            # 打印日志：本轮调用了哪个工具
            print(f"  工具: {tool_name}")
            # 打印日志：工具收到了什么参数
            print(f"  输入: {json.dumps(tool_args, ensure_ascii=False)}")

            # 真正执行工具：根据工具名走对应分支，拿到字符串结果
            result = execute_tool(tool_name, tool_args)

            # 打印日志：工具返回了什么
            print(f"  输出: {result}\n")

            # 把工具执行结果作为 user 消息追加回对话历史
            # DeepSeek/OpenAI 约定工具结果的消息格式：
            #   {"role": "tool",
            #    "tool_call_id": 对应工具调用的 id（必须跟上面 assistant_message 里的 id 匹配）,
            #    "content": 工具返回的字符串结果}
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result
            })

    # 超过 max_steps 仍未结束的兜底返回；此时 _memory 里可能已有部分数据
    return "已达到最大步数上限。部分结果已保存在记忆中。"


# ─── 启动示例（直接运行此文件才会执行，被 import 时不会触发） ────────────────────

# Python 惯用写法：只有当文件被直接运行（python deepseek_agent.py）时才执行以下代码
if __name__ == "__main__":
    # 调用智能体主函数，传入一个示例任务描述
    run_agent(
        # 任务描述第 1 句：计算复利终值
        "我想用 5000 美元按 7% 的年复利投资 5 年。"
        # 任务描述第 2 句：写入记忆
        "先计算最终金额，把结果以 'investment_result' 为键名保存到记忆，"
        # 任务描述第 3 句：读取记忆以验证
        "然后把它读取出来以确认保存成功，"
        # 任务描述第 4 句：联网搜信息
        "再去网络上搜索最新的智能体 AI 发展趋势，"
        # 任务描述第 5 句：让模型综合给出最终答复
        "最后写一小段话，总结投资结果和你找到的关键 AI 趋势。"
    )