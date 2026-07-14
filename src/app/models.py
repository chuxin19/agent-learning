"""DeepSeek API 客户端封装：初始化 client + 带超时/指数退避重试的 call_api。

原来在 deepseek_agent.py 顶层：
  - client = OpenAI(base_url=..., api_key=...)   （模块级全局）
  - def call_api(messages, config)               （依赖全局 client 和 tools）

现在改为：
  - get_client() → 创建并返回一个 OpenAI client（延迟创建，按需调用）
  - call_api(client, messages, tools, config) → 显式接收所有依赖，无全局状态

这样做的好处:
  1. 可以创建多个 client（比如不同 API Key、不同模型）
  2. 单元测试时可以传 fake client
  3. 代码可读性更好（一眼看出函数依赖什么）
"""

import os
import time
from openai import OpenAI

from .config import AgentConfig


def get_client() -> OpenAI:
    """创建并返回一个配置好的 DeepSeek API client。

    使用环境变量 DEEPSEEK_API_KEY 作为 API Key（由顶部 load_dotenv 加载的 .env 文件提供）。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY 未设置。请在项目根目录创建一个 .env 文件，"
            "写入 DEEPSEEK_API_KEY=你的key，然后再运行。"
            "参考文件: .env.example"
        )
    return OpenAI(
        base_url="https://api.deepseek.com",
        api_key=api_key,
    )


def call_api(
    client: OpenAI,
    messages: list[dict],
    tools: list[dict],
    config: AgentConfig,
) -> object:
    """调用 DeepSeek API，带超时控制和指数退避重试。

    参数:
        client:   OpenAI 兼容客户端实例（由 get_client() 创建）
        messages: 当前对话历史（跟直接传给 client.chat.completions.create 的一样）
        tools:    工具定义列表（JSON Schema 格式，给模型看"我能做什么"）
        config:   AgentConfig 配置对象，决定 model、max_tokens、timeout、重试次数等

    返回:
        跟 client.chat.completions.create() 完全一样的响应对象

    失败策略:
        指数退避: 第 1 次失败 → 等 config.retry_base_wait 秒 → 重试
                  第 2 次失败 → 等 2 × base_wait 秒 → 重试
                  ...
                  第 config.retry_max_attempts 次失败 → 真的失败，抛出异常
        等待时间逐次翻倍，给服务器喘息时间，避免 DDoS 式的重试。
    """
    for attempt in range(config.retry_max_attempts):
        try:
            return client.chat.completions.create(
                model=config.model_name,
                max_tokens=config.max_tokens_per_call,
                temperature=config.temperature,
                tools=tools,
                tool_choice="auto",
                messages=messages,
                timeout=config.api_timeout,
            )
        except Exception as e:
            if attempt == config.retry_max_attempts - 1:
                raise
            wait_seconds = config.retry_base_wait * (2 ** attempt)
            print(f"  ⚠️  API 调用失败（第 {attempt + 1} 次）: {e}")
            print(f"  ⏳  {wait_seconds} 秒后重试...")
            time.sleep(wait_seconds)

    raise RuntimeError("API 调用失败：已达最大重试次数")