"""记忆管理：智能体的长期记忆，支持读写到 JSON 文件。

封装了以下能力:
  - 启动时从 data/agent_memory.json 加载已有内容
  - save/recall/list/delete 四种 CRUD 操作
  - 每条记忆自动带 created_at / updated_at 元数据
  - 向后兼容旧格式（简单的 {key: value}）

原来在 deepseek_agent.py 顶层的全局 _memory 字典、
_load_memory / _save_memory / _timestamp 三个函数，
现在全部封装进 MemoryStore 类，由实例持有状态。
"""

import json
import os
import datetime


# 记忆持久化文件路径
MEMORY_FILE = "data/agent_memory.json"


def _timestamp() -> str:
    """生成 ISO 格式时间戳，例如 '2026-07-14T10:30:15'。"""
    return datetime.datetime.now().isoformat(timespec="seconds")


class MemoryStore:
    """智能体的持久化记忆仓库。每个实例持有一份独立的内存 dict。

    记忆结构:
        {
          "investment_result": {
            "value":      "5000美元按7%年复利投资5年...",
            "created_at": "2026-07-14T10:30:15",
            "updated_at": "2026-07-14T10:30:15"
          }
        }
    """

    def __init__(self, memory_file: str = MEMORY_FILE):
        """初始化: 从文件加载已有记忆（文件不存在则为空）。"""
        self.memory_file = memory_file
        self._memory: dict[str, dict] = self._load_memory()

    # ──────────────── 文件读写（内部方法） ────────────────

    def _load_memory(self) -> dict[str, dict]:
        """从 JSON 文件读取已保存的记忆，返回 dict。文件不存在或解析失败时返回空字典。"""
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}

                result = {}
                for k, v in data.items():
                    if isinstance(v, dict) and "value" in v:
                        # 新格式：直接使用
                        result[str(k)] = {
                            "value": str(v["value"]),
                            "created_at": v.get("created_at", _timestamp()),
                            "updated_at": v.get("updated_at", _timestamp()),
                        }
                    else:
                        # 老格式（简单字符串）：升级到新格式，时间填当前时间
                        now = _timestamp()
                        result[str(k)] = {
                            "value": str(v),
                            "created_at": now,
                            "updated_at": now,
                        }
                return result
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"  ⚠️  加载记忆文件失败: {e}")
            return {}

    def _save_memory(self) -> None:
        """把当前记忆写到文件。失败时只打印警告，不崩溃（记忆持久化是"锦上添花"）。"""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️  保存记忆文件失败: {e}")

    # ──────────────── 对外 API（供 execute_tool 调用） ────────────────

    def save(self, key: str, value: str) -> str:
        """写入 key-value 到记忆。如果 key 已存在，保留 created_at，只更新 value 和 updated_at。"""
        now = _timestamp()

        if key in self._memory and isinstance(self._memory[key], dict) and "created_at" in self._memory[key]:
            self._memory[key]["value"] = value
            self._memory[key]["updated_at"] = now
        else:
            self._memory[key] = {
                "value": value,
                "created_at": now,
                "updated_at": now,
            }

        # 同步到文件
        self._save_memory()

        entry = self._memory[key]
        return f"已保存 '{key}' = '{value}' (created_at={entry['created_at']}, updated_at={entry['updated_at']})"

    def recall(self, key: str) -> str:
        """根据 key 读取记忆（返回 value + 元数据）。找不到返回提示文字。"""
        entry = self._memory.get(key)
        if isinstance(entry, dict) and "value" in entry:
            return f"{entry['value']} (created_at={entry['created_at']}, updated_at={entry['updated_at']})"
        return f"未找到记忆项 '{key}'"

    def list_all(self) -> str:
        """列出所有记忆 key 及元数据摘要。"""
        if not self._memory:
            return "记忆为空"

        lines = [f"共 {len(self._memory)} 项记忆:"]
        for key, entry in self._memory.items():
            if isinstance(entry, dict) and "value" in entry:
                v = entry["value"]
                lines.append(
                    f"  - {key}: {v[:50]}{'...' if len(v) > 50 else ''}"
                    f" (created_at={entry['created_at']}, updated_at={entry['updated_at']})"
                )
            else:
                lines.append(f"  - {key}: {entry} (老格式，已在加载时升级)")
        return "\n".join(lines)

    def delete(self, key: str) -> str:
        """删除指定 key 的记忆。"""
        if key in self._memory:
            del self._memory[key]
            self._save_memory()
            return f"已删除记忆项 '{key}'"
        return f"未找到记忆项 '{key}'，无需删除"

    def reload(self) -> None:
        """从磁盘重新加载记忆文件（仅在你手动改了 JSON 文件时需要调用）。"""
        self._memory = self._load_memory()

    # ──────────────── 辅助方法（供 agent.py 构造"记忆摘要"给模型看） ────────────────

    def to_context_text(self) -> str:
        """把当前记忆格式化为一行文字，塞给模型让它"知道之前存过什么"。

        返回的格式类似:
          "You have access to persistent memory. Current memory contents:
             - investment_result: 5000美元按7%年复利投资5年，最终金额为7012.76美元 (created_at=..., updated_at=...)"
        """
        if not self._memory:
            return (
                "You have access to persistent memory. "
                "Your memory is currently empty (no prior information stored). "
                "Feel free to save useful intermediate results for future use. "
            )

        lines = []
        for key, entry in self._memory.items():
            if isinstance(entry, dict) and "value" in entry:
                v = entry["value"]
                lines.append(
                    f"  - {key}: {v[:60]}{'...' if len(v) > 60 else ''}"
                    f" (created_at={entry['created_at']}, updated_at={entry['updated_at']})"
                )
            else:
                lines.append(f"  - {key}: {entry}")

        return (
            "You have access to persistent memory. "
            "Before starting your task, check this memory first. "
            "If relevant information already exists, recall it instead of re-compute things. "
            f"Current memory contents:\n" + "\n".join(lines) + "\n"
        )