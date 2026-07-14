"""app —— 基于 DeepSeek API 的 ai 智能体学习项目。

便捷导出：
  - 运行 agent:     run_agent
  - 配置:           AgentConfig, DEFAULT_CONFIG
  - 记忆:           MemoryStore
  - API 客户端:     get_client, call_api
  - 工具系统（新增）: ToolRegistry, ToolContext, register_tool, get_global_registry
"""

from .config import AgentConfig, DEFAULT_CONFIG
from .memory import MemoryStore
from .models import get_client, call_api
from .tools import ToolRegistry, ToolContext, register_tool, get_global_registry
from .agent import run_agent

__all__ = [
    "run_agent",
    "AgentConfig",
    "DEFAULT_CONFIG",
    "MemoryStore",
    "get_client",
    "call_api",
    "ToolRegistry",
    "ToolContext",
    "register_tool",
    "get_global_registry",
]