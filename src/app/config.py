"""集中管理智能体运行时的所有可调参数。

以后想调参就改这里，不用去翻 run_agent 和 call_api 里的数字了。

示例:
    from app.config import AgentConfig

    config = AgentConfig(max_steps=10, temperature=0.9)   # 调温度
    config = AgentConfig(max_tokens_per_call=512)         # 限制单次输出长度
"""

from dataclasses import dataclass


@dataclass
class AgentConfig:
    """智能体运行时的所有可调参数，集中管理，方便调参。"""

    # ── 模型相关
    model_name: str = "deepseek-chat"
    # 温度：0=最确定，1=最有创造力。陪伴型助手建议 0.7-0.9
    temperature: float = 0.8

    # ── 循环控制
    max_steps: int = 15

    # ── API 调用相关
    # 单次 API 调用最多输出多少 token，防止长篇大论烧钱
    max_tokens_per_call: int = 1024
    # API 超时秒数，防止卡死
    api_timeout: int = 30

    # ── 重试相关
    # 失败最多重试几次
    retry_max_attempts: int = 3
    # 第一次重试的等待秒数（指数退避：后续每次翻倍）
    retry_base_wait: int = 2

    # ── 费用监控（单位：美元 / 1M tokens）
    # 2025 年 DeepSeek 平台定价（你可以随时手动更新）
    cost_input_per_million: float = 0.14
    cost_output_per_million: float = 0.28


# 默认配置：大部分时候用它就够了
DEFAULT_CONFIG = AgentConfig()