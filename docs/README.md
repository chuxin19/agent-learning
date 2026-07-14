# agent-learning — 智能体学习项目

一个从零构建 ai 智能体（思考 → 行动 → 观察 → 循环完成任务）。本项目使用 DeepSeek API，兼容 OpenAI 协议。依赖管理使用 **uv**（类似 npm 的体验，装完自动记录依赖）。

---

## 📦 项目文件一览

| 文件 | 作用 |
|------|------|
| `deepseek_agent.py` | 主程序：完整 ai 智能体（推荐使用） |
| `anthropic_agent.py` | 备用：使用 Anthropic Claude 的版本（英文注释） |
| `anthropic_agent_zh.py` | 备用：使用 Anthropic Claude 的版本（中文注释） |
| `pyproject.toml` | 项目配置 + 依赖声明（类似 package.json，由 uv 自动生成） |
| `uv.lock` | 精确锁定依赖版本（类似 package-lock.json，由 uv 自动生成） |
| `.env.example` | API Key 模板（复制为 `.env` 后填入真实 key） |
| `mise.toml` | mise 版本管理：锁定本项目使用 Python 3.14.6 |
| `.gitignore` | Git 忽略规则（含虚拟环境、.env 等） |

---

## 🚀 从零搭建 Agent 的标准化步骤（uv 方式）

以后你想新建一个 agent 项目时，按以下步骤走：

### 第 1 步：用 mise 锁定 Python 版本

在项目根目录执行：

```bash
# 锁定 Python 版本（确保团队/换机器时版本一致）
# 这会在项目目录下生成 mise.toml
mise use python@3.14.6

# 确认版本
python --version
```

生成的 `mise.toml` 内容：

```toml
[tools]
python = "3.14.6"
```

> 💡 **为什么用 mise**：让团队/换机器时，保证所有人用的 Python 版本一致，避免"我机器上能跑你机器上不能跑"的问题。

---

### 第 2 步：用 uv 创建虚拟环境

```bash
# 在项目根目录创建虚拟环境
uv venv

# 激活虚拟环境（Mac / Linux）
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

# 确认激活成功（应该看到 .../.venv/bin/python
which python
```

> 💡 **uv 会自动识别 mise 提供的 Python，创建干净的项目依赖环境，跟系统 Python 隔离。

---

### 第 3 步：用 uv init 初始化项目（类似 npm init）

```bash
uv init
```

**这一步会创建 `pyproject.toml`**（类似 npm 的 package.json）。

> 💡 **关键点**：`uv add xxx` 需要先有 `pyproject.toml`，否则会报错 "No pyproject.toml found"。

---

### 第 4 步：用 uv add 安装依赖（自动记录）

**这就是 uv 跟 npm 一样的地方：装完自动记录到 `pyproject.toml`。**

```bash
# 装 deepseek 需要的两个依赖：

# 1. DeepSeek API 兼容 OpenAI 协议，所以用 openai 库
uv add openai

# 2. 读取 .env 文件中的环境变量
uv add python-dotenv
```

**装完以后，项目根目录会自动生成两个文件：

- `pyproject.toml`（类似 package.json，记录你声明的依赖）
- `uv.lock`（类似 package-lock.json，精确锁版本）

> 💡 **uv add = npm install --save**，每次 `uv add xxx`，就像 `npm install xxx --save`，自动记录。

> 💡 **常见的 Agent 依赖组合**：
> - **DeepSeek**：`uv add openai`（DeepSeek 兼容 OpenAI 协议）
> - **Claude**：`uv add anthropic`（Anthropic 官方 SDK）
> - **配置文件读取**：`uv add python-dotenv`
> - **联网搜索**：`uv add requests` 或 `uv add duckduckgo-search`

---

### 第 5 步：以后拿到项目只需一条命令

如果别人拿到你的项目（或你换机器），只需：

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 根据 pyproject.toml 和 uv.lock 自动安装所有依赖（类似 npm install）
uv sync
```

---

### 第 6 步：配置 API Key（`.env` 文件）

```bash
# 从模板复制
cp .env.example .env
```

打开 `.env`，把 `YOUR_KEY_HERE` 替换成真实 key：

```env
DEEPSEEK_API_KEY=你的真实key
```

> 💡 `.gitignore` 里已忽略 `.env`，key 不会被意外提交到 Git。

---

### 第 7 步：在代码里初始化客户端

在 Python 文件顶部：

```python
from dotenv import load_dotenv
import os
from openai import OpenAI

# 必须放在客户端初始化之前
load_dotenv()

# 初始化客户端：告诉 openai 库去 api.deepseek.com
client = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY")
)
```

---

### 第 8 步：定义 tools

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a mathematical expression and return the numeric result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            }
        }
    }
]
```

---

### 第 9 步：写主循环

```python
import json

while step < max_steps:
    response = client.chat.completions.create(
        model="deepseek-chat",
        tools=tools,
        tool_choice="auto",
        messages=messages
    )

    # 判断是否结束
    if response.choices[0].finish_reason == "stop":
        return response.choices[0].message.content

    # 否则处理工具调用
    for tool_call in response.choices[0].message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        result = execute_tool(tool_name, tool_args)

        messages.append({"role": "assistant", "tool_calls": response.choices[0].message.tool_calls})
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
```

---

### 第 10 步：运行

```bash
python deepseek_agent.py
```

---

## 🔑 环境搭建关键点总结（uv 方式）

| 步骤 | 文件 / 命令 | 一句话说明 |
|------|-------------|-----------|
| 锁定 Python | `mise use python@3.14.6` | 生成 `mise.toml`，保证版本一致 |
| 虚拟环境 | `uv venv` + `source .venv/bin/activate` | 隔离项目依赖 |
| **项目初始化** | `uv init` | 创建 `pyproject.toml`，类似 `npm init` |
| 安装依赖 | `uv add openai`、`uv add python-dotenv` | 装完自动记录到 `pyproject.toml` |
| 一键恢复 | `uv sync` | 类似 `npm install`，根据 lock 文件精确安装 |
| API Key | `.env.example` → `.env` | 模板复制为真实配置，绝不提交到 Git |
| 客户端初始化 | `OpenAI(base_url="https://api.deepseek.com", api_key=...)` | DeepSeek 兼容 OpenAI 协议 |
| 工具定义 | `tools` 列表 | 告诉模型"我能做什么" |
| 主循环 | while 循环 + finish_reason 判断 | ai 模式的核心 |

---

## 📊 uv vs pip 对比表

| 操作 | npm | uv | pip |
|------|-----|-----|-----|
| 创建虚拟环境 | — | `uv venv` | `python -m venv .venv` |
| 初始化项目（创建配置文件） | `npm init` | `uv init` | 手动创建 `requirements.txt` |
| 装包 + 自动记录 | `npm install xxx` | `uv add xxx` | `pip install xxx`（❌ 不自动记录） |
| 根据 lock 安装 | `npm install` | `uv sync` | `pip install -r requirements.txt` |
| 配置文件 | `package.json` | `pyproject.toml` | `requirements.txt` |
| 锁版本 | `package-lock.json` | `uv.lock` | 手动 `pip freeze` |

---

## 📖 DeepSeek API 小提示

- **平台**：https://platform.deepseek.com
- **模型名**：`deepseek-chat`（支持 tool calling）
- **API 协议**：完全兼容 OpenAI，所以用 `openai` 库，只需改 `base_url`
- **费用**：按 token 计费，新用户有免费额度

---

## 🎯 本项目快速启动

当前这个项目已经准备好 `pyproject.toml`（由 `uv init` 生成的），直接按以下步骤就能跑：

```bash
# 1. 确认 Python 版本
python --version

# 2. 用 uv 创建虚拟环境
uv venv

# 3. 激活虚拟环境
source .venv/bin/activate

# 4. 安装依赖（根据 pyproject.toml 自动安装）
uv sync

# 5. 配置 API Key
cp .env.example .env
# 然后编辑 .env，把 YOUR_KEY_HERE 替换成真实 DEEPSEEK_API_KEY

# 6. 运行
python deepseek_agent.py
```

> 💡 **如果是从零新建项目（还没有 pyproject.toml），完整流程是：
>
> ```bash
> uv venv
> source .venv/bin/activate
> uv init
> uv add openai
> uv add python-dotenv
> ```
>
> `uv init` 这一步必不可少——它会创建 `pyproject.toml`，否则 `uv add` 会报错 "No pyproject.toml found"。

---

## 📌 uv 常用命令速查

| 命令 | 效果 |
|------|------|
| `uv venv` | 创建虚拟环境 |
| `uv init` | 初始化项目，创建 `pyproject.toml`（类似 `npm init`） |
| `uv add xxx` | 装包 + 自动记录到 pyproject.toml |
| `uv sync` | 根据 lock 文件精确安装所有依赖 |
| `uv pip install xxx` | 装包但不记录（跟 pip 一样） |
| `uv remove xxx` | 卸载包并从 pyproject.toml 中移除 |