"""记忆管理：智能体的长期记忆，按分类存储，支持读写到 JSON 文件。

分类结构（相比旧版扁平的 {key: value}）:
    {
      "_meta":         { "schema_version": "1.0", ... },
      "profile":       { "name": { "value": "Allen", ... }, ... },
      "preferences":   { "communication_style": { "value": "直接但礼貌", ... }, ... },
      "work":          { ... },
      "family":        { ... },
      "life":          { ... },
      "general":       { ... }
    }

分类说明:
    - profile:     用户画像（姓名、职业、基本信息）
    - preferences: 用户偏好（沟通风格、感兴趣的话题）
    - work:        工作相关（项目、同事、目标）
    - family:      家庭成员和关系
    - life:        健康、兴趣、生活琐事
    - general:     临时笔记、中间计算结果

向后兼容:
    - 如果 data/agent_memory.json 是旧的扁平格式（{key: value}），
      启动时会自动迁移到 general 分类，旧数据不会丢失。
"""

import json
import os
import datetime


# 记忆持久化文件路径
MEMORY_FILE = "data/agent_memory.json"

# 预设的分类列表（也是默认创建的分类）
DEFAULT_CATEGORIES = [
    "profile",
    "preferences",
    "work",
    "family",
    "life",
    "general",
]


def _timestamp() -> str:
    """生成 ISO 格式时间戳，例如 '2026-07-14T10:30:15'。"""
    return datetime.datetime.now().isoformat(timespec="seconds")


class MemoryStore:
    """智能体的持久化记忆仓库。

    每个实例持有一份独立的内存 dict（即分类 → key → entry）。
    entry 结构:
        { "value": "...", "created_at": "...", "updated_at": "..." }
    """

    def __init__(self, memory_file: str = MEMORY_FILE):
        """初始化: 从文件加载已有记忆（文件不存在则为空）。"""
        self.memory_file = memory_file
        self._data: dict[str, dict] = self._load_memory()

    # ──────────────── 文件读写（内部方法） ────────────────

    def _ensure_structure(self) -> None:
        """确保 _data 有 _meta 和全部默认分类。"""
        if "_meta" not in self._data:
            self._data["_meta"] = {
                "schema_version": "1.0",
                "owner": "",
                "created_at": _timestamp(),
            }
        for cat in DEFAULT_CATEGORIES:
            if cat not in self._data:
                self._data[cat] = {}

    def _load_memory(self) -> dict[str, dict]:
        """从 JSON 文件读取已保存的记忆。

        支持两种文件格式:
          1) 新格式（分类结构）:
              {"_meta": {...}, "profile": {...}, "work": {...}}
          2) 旧格式（扁平 key-value）:
              {"key": "string_value"}  →  自动迁移到 general 分类
        """
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if not isinstance(raw, dict):
                    self._data = {}
                    self._ensure_structure()
                    return self._data

                # ── 检测是否为新格式（有 _meta 字段或任一分类字段） ──
                is_new_format = (
                    "_meta" in raw
                    or any(k in DEFAULT_CATEGORIES for k in raw.keys())
                )

                if is_new_format:
                    # 新格式：直接使用，确保分类齐全
                    self._data = raw
                    self._ensure_structure()
                    return self._data
                else:
                    # 旧格式（扁平 key-value）：迁移到 general 分类
                    now = _timestamp()
                    self._data = {}
                    self._ensure_structure()
                    for k, v in raw.items():
                        self._data["general"][str(k)] = {
                            "value": str(v),
                            "created_at": now,
                            "updated_at": now,
                        }
                    print(
                        f"  ⓘ  检测到旧格式记忆文件，已迁移 {len(raw)} 项到 general 分类"
                    )
                    self._save_memory()
                    return self._data

        except FileNotFoundError:
            self._data = {}
            self._ensure_structure()
            return self._data
        except Exception as e:
            print(f"  ⚠️  加载记忆文件失败: {e}")
            self._data = {}
            self._ensure_structure()
            return self._data

    def _save_memory(self) -> None:
        """把当前记忆写到文件。失败时只打印警告，不崩溃。"""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️  保存记忆文件失败: {e}")

    # ──────────────── 对外 API（供工具调用和脚本使用） ────────────────

    def save_user_input(self, text: str) -> str:
        """系统自动记录用户的输入（不依赖模型主动调用 save_memory）。

        - 存到 life 分类下
        - key 格式：user_input_0001_2026-07-14T10:30:15
        - value 格式：[第1次输入 2026-07-14 10:30] 今天被老板批评了
        - 序号在 _meta 中维护（自增），保证不重复、不遗漏
        这样即使用户只说了一句话，也会被记录下来，未来对话时模型能看到。
        """
        if not text or not text.strip():
            return ""

        now = _timestamp()
        date_time_display = now.replace("T", " ")[:16]  # "2026-07-14 10:30"

        # 从 _meta 读取自增序号，没有就从 1 开始
        meta = self._data.get("_meta", {})
        seq = int(meta.get("user_input_count", 0)) + 1
        meta["user_input_count"] = seq
        self._data["_meta"] = meta

        # key 用 4 位序号补零 + 时间戳，保证排序和唯一
        seq_padded = f"{seq:04d}"
        key = f"user_input_{seq_padded}_{now}"
        value = f"[第{seq}次输入 {date_time_display}] {text.strip()}"

        category = "life"
        if category not in self._data:
            self._data[category] = {}
        self._data[category][key] = {
            "value": value,
            "created_at": now,
            "updated_at": now,
        }
        self._save_memory()
        return f"已自动记录用户输入到 [{category}] '{key}'（第{seq}次）"

    def save(self, category: str, key: str, value: str) -> str:
        """写入一条记忆到指定分类。

        如果该分类下的 key 已存在，保留 created_at，只更新 value 和 updated_at。
        """
        category = category.strip().lower()
        if category not in self._data:
            # 未知分类：自动创建（允许 agent 动态创建新分类）
            self._data[category] = {}

        now = _timestamp()
        existing = self._data[category].get(key)

        if isinstance(existing, dict) and "created_at" in existing:
            existing["value"] = value
            existing["updated_at"] = now
        else:
            self._data[category][key] = {
                "value": value,
                "created_at": now,
                "updated_at": now,
            }

        self._save_memory()
        entry = self._data[category][key]
        return (
            f"已保存到 [{category}] '{key}' = '{value}' "
            f"(created_at={entry['created_at']}, updated_at={entry['updated_at']})"
        )

    def recall(self, category: str, key: str) -> str:
        """从指定分类读取一条记忆（返回 value + 元数据）。找不到时返回提示文字。"""
        category = category.strip().lower()
        if category not in self._data:
            return f"未知分类: '{category}'（可用分类: {', '.join(self.list_categories())}）"

        entry = self._data[category].get(key)
        if isinstance(entry, dict) and "value" in entry:
            return f"[{category}] {key}: {entry['value']} (created_at={entry['created_at']}, updated_at={entry['updated_at']})"
        return f"[{category}] 未找到 '{key}'"

    def list_category(self, category: str) -> str:
        """列出指定分类下的所有记忆条目。"""
        category = category.strip().lower()
        if category not in self._data:
            return f"未知分类: '{category}'"

        entries = self._data[category]
        if not entries:
            return f"[{category}] 分类为空"

        lines = [f"[{category}] 共 {len(entries)} 项:"]
        for key, entry in entries.items():
            if isinstance(entry, dict) and "value" in entry:
                v = entry["value"]
                lines.append(
                    f"  - {key}: {v[:60]}{'...' if len(v) > 60 else ''}"
                    f" (updated_at={entry['updated_at']})"
                )
            else:
                lines.append(f"  - {key}: {entry}")
        return "\n".join(lines)

    def list_all(self) -> str:
        """列出全部分类的摘要（每个分类显示有多少条记忆）。"""
        summary = []
        for cat in DEFAULT_CATEGORIES:
            entries = self._data.get(cat, {})
            summary.append(f"  - {cat}: {len(entries)} 项")

        # 动态创建的分类也一并列出
        for cat in sorted(self._data.keys()):
            if cat == "_meta" or cat in DEFAULT_CATEGORIES:
                continue
            entries = self._data[cat]
            summary.append(f"  - {cat}: {len(entries)} 项 (动态创建)")

        return "记忆摘要:\n" + "\n".join(summary)

    def list_categories(self) -> list[str]:
        """返回所有当前有数据的分类名列表（按默认顺序 + 动态创建的分类）。"""
        cats = []
        for cat in DEFAULT_CATEGORIES:
            if self._data.get(cat):
                cats.append(cat)
        for cat in sorted(self._data.keys()):
            if cat != "_meta" and cat not in DEFAULT_CATEGORIES and self._data[cat]:
                cats.append(cat)
        return cats

    def delete(self, category: str, key: str) -> str:
        """从指定分类删除一条记忆。"""
        category = category.strip().lower()
        if category not in self._data:
            return f"未知分类: '{category}'"

        if key in self._data[category]:
            del self._data[category][key]
            self._save_memory()
            return f"[{category}] 已删除 '{key}'"
        return f"[{category}] 未找到 '{key}'，无需删除"

    def search(self, keyword: str) -> str:
        """跨分类搜索关键词，返回匹配的条目列表。"""
        keyword_lower = keyword.strip().lower()
        if not keyword_lower:
            return "搜索关键词不能为空"

        matches = []
        for cat, entries in self._data.items():
            if cat == "_meta" or not isinstance(entries, dict):
                continue
            for key, entry in entries.items():
                if not isinstance(entry, dict) or "value" not in entry:
                    continue
                # 在 key 和 value 中搜索（不区分大小写）
                if (
                    keyword_lower in key.lower()
                    or keyword_lower in str(entry["value"]).lower()
                ):
                    v = entry["value"]
                    matches.append(
                        f"  - [{cat}] {key}: {v[:80]}{'...' if len(str(v)) > 80 else ''}"
                    )

        if matches:
            return f"搜索 '{keyword}' 匹配到 {len(matches)} 项:\n" + "\n".join(matches)
        return f"搜索 '{keyword}' 未找到匹配项"

    def reload(self) -> None:
        """从磁盘重新加载记忆文件（仅在你手动改了 JSON 文件时需要调用）。"""
        self._data = self._load_memory()

    # ──────────────── 辅助方法（供 agent 构造"记忆摘要"给模型看） ────────────────

    def to_context_text(self) -> str:
        """把当前记忆格式化为一段文字，塞给模型让它"知道之前存过什么"。

        返回的格式类似:
          "You have access to persistent, organized memory...
           - profile: name=Allen (updated_at=...)
           - general: investment_result=7012.76 (updated_at=...)
          "
        """
        # 检查是否为空（_meta 除外）
        is_empty = all(
            not self._data.get(cat)
            for cat in DEFAULT_CATEGORIES
        ) and not any(
            isinstance(v, dict) and v
            for k, v in self._data.items()
            if k not in DEFAULT_CATEGORIES and k != "_meta"
        )

        if is_empty:
            return (
                "You have access to persistent, organized memory. "
                "Your memory is currently empty —— no prior information stored. "
                "Use save_memory to record useful information as you work."
            )

        lines = []
        for cat in DEFAULT_CATEGORIES:
            entries = self._data.get(cat, {})
            if not entries:
                continue
            for key, entry in entries.items():
                if isinstance(entry, dict) and "value" in entry:
                    v = entry["value"]
                    lines.append(
                        f"  - {cat}.{key}: {v[:80]}{'...' if len(str(v)) > 80 else ''}"
                        f" (updated_at={entry['updated_at']})"
                    )

        # 动态创建的分类
        for cat in sorted(self._data.keys()):
            if cat == "_meta" or cat in DEFAULT_CATEGORIES or not isinstance(
                self._data[cat], dict
            ):
                continue
            for key, entry in self._data[cat].items():
                if isinstance(entry, dict) and "value" in entry:
                    v = entry["value"]
                    lines.append(
                        f"  - {cat}.{key}: {v[:80]}{'...' if len(str(v)) > 80 else ''}"
                        f" (updated_at={entry['updated_at']})"
                    )

        return (
            "You have access to persistent, organized memory. "
            "Memory is organized into categories: profile, preferences, work, family, life, general. "
            "If relevant information is already in memory, recall it before re-computing or re-asking. "
            f"Current memory contents:\n" + "\n".join(lines) + "\n"
        )