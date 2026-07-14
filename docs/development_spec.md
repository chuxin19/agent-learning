# 开发规范

---

## 一、分支管理规范

### 1. 长期分支

| 分支名 | 用途 |
|--------|------|
| `main` | 最基础的入门代码，稳定版本，供新人快速上手 |
| `agent_v1` | 第一阶段学习完成的版本 |
| `agent_v2` | 第二阶段学习完成的版本 |
| `agent_v3` | 第三阶段学习完成的版本 |

### 2. 临时分支

| 分支命名 | 用途 | 生命周期 |
|---------|------|---------|
| `feature/xxx` | 新功能开发 | 开发完成后合并到对应版本分支，然后删除 |
| `fix/xxx` | Bug 修复 | 修复完成后合并，然后删除 |
| `experiment/xxx` | 实验性代码 | 实验结束后直接删除 |

### 3. 分支操作流程

```bash
# 创建新功能分支
git checkout agent_v1
git checkout -b feature/new-tool

# 开发完成后合并回 agent_v1
git checkout agent_v1
git merge feature/new-tool

# 删除临时分支
git branch -d feature/new-tool
git push origin --delete feature/new-tool
```

---

## 二、Commit 信息规范

### 1. 格式

```
<类型>: <简要描述>
```

### 2. 类型说明

| 类型 | 说明 | 示例 |
|------|------|------|
| `init` | 初始提交 | `init: 初始化项目` |
| `feat` | 新功能 | `feat: 添加网络搜索工具` |
| `fix` | Bug 修复 | `fix: 修复 Token 计算错误` |
| `refactor` | 代码重构 | `refactor: 重写记忆存储模块` |
| `docs` | 文档更新 | `docs: 更新 README 使用说明` |
| `chore` | 构建/工具链调整 | `chore: 更新依赖版本` |
| `test` | 测试相关 | `test: 添加工具调用测试` |

### 3. 示例

```
feat: 实现复利计算工具
fix: 修复环境变量加载失败的问题
refactor: 重构 agent 主循环
chore: 升级 openai SDK 到最新版本
```

---

## 三、版本命名规范

### 版本号格式：`MAJOR.MINOR.PATCH`

| 部分 | 说明 | 何时递增 |
|------|------|---------|
| `MAJOR` | 主版本号 | 大重构、不兼容的 API 变更（初期保持 0） |
| `MINOR` | 次版本号 | 新增功能模块、接入新框架 |
| `PATCH` | 补丁版本号 | Bug 修复、小优化、文档更新 |

### 递增规则：每次只 +1，不能跳级

| 当前版本 | 下一个版本 | 场景 |
|---------|-----------|------|
| `0.0.1` | `0.0.2` | 修复 Bug、小调整 |
| `0.0.2` | `0.0.3` | 继续小优化 |
| `0.0.x` → | `0.1.0` | 第一阶段功能完成（较大功能更新） |
| `0.1.0` | `0.1.1` | Bug 修复 |
| `0.1.x` → | `0.2.0` | 第二阶段功能完成（接入新框架） |
| `0.2.x` → | `0.3.0` | 第三阶段功能完成 |
| `0.x.x` → | `1.0.0` | 完整功能版本，正式发布 |

### 项目演进路径示例

```
0.0.1  →  初始版本
0.0.2  →  修复 Token 计算 bug
0.0.3  →  优化日志输出
0.1.0  →  第一阶段完成：DeepSeek API + Token 统计 + 记忆存储
0.1.1  →  修复记忆存储路径问题
0.2.0  →  第二阶段完成：接入 Agent SDK/框架
0.2.1  →  优化框架集成
0.3.0  →  第三阶段完成：更多功能...
1.0.0  →  完整功能版本
```

### 在 `pyproject.toml` 中更新

```toml
[project]
name = "agent-learning"
version = "0.0.1"
authors = [
    { name = "Allen", email = "andyrubindreamer@gmail.com" },
]
```

---

## 四、安全规范

### 1. API Key 永远不要提交

- `.env` 文件已在 `.gitignore` 中
- 永远不要在代码中硬编码 API Key
- 使用环境变量或 `.env` 文件管理密钥

### 2. 敏感信息检查

提交前确认：

```bash
# 查看即将提交的文件
git status

# 确认 .env 不在待提交列表中
```

---

## 五、项目文件结构

```
agent-learning/
├── src/
│   └── app/              # 核心代码目录
│       ├── __init__.py
│       ├── agent.py      # Agent 主逻辑
│       ├── config.py     # 配置
│       ├── memory.py     # 记忆存储
│       ├── models.py     # 模型客户端
│       └── tools.py      # 工具定义
├── main.py               # 入口脚本
├── pyproject.toml        # 项目配置 + 依赖
├── uv.lock               # 精确锁定依赖版本
├── .env                  # API Key（不提交）
├── .env.example          # Key 模板（提交）
├── .gitignore            # Git 忽略规则
├── docs/                 # 文档
├── data/                 # 数据文件
└── .venv/                # 虚拟环境（不提交）
```

---

## 六、开发流程速查

### 新建项目环境

```bash
cd /Users/nova/Documents/Code/agent-learning
uv venv
source .venv/bin/activate
uv sync
```

### 日常开发

```bash
# 1. 切到目标版本分支
git checkout agent_v1

# 2. 拉取最新代码
git pull

# 3. 创建功能分支
git checkout -b feature/xxx

# 4. 开发 & 提交
git add .
git commit -m "feat: xxx"

# 5. 合并回版本分支
git checkout agent_v1
git merge feature/xxx

# 6. 推送
git push

# 7. 删除临时分支
git branch -d feature/xxx
```

### 运行项目

```bash
# 方式一：uv run（自动处理环境）
uv run python main.py

# 方式二：激活环境后运行
source .venv/bin/activate
python main.py
```

---

## 七、Git 常用命令速查

| 命令 | 用途 |
|------|------|
| `git status` | 查看当前状态 |
| `git branch` | 查看本地分支 |
| `git branch -a` | 查看所有分支（含远程） |
| `git checkout <branch>` | 切换分支 |
| `git checkout -b <branch>` | 创建并切换到新分支 |
| `git add .` | 添加所有文件到暂存区 |
| `git commit -m "msg"` | 提交 |
| `git push -u origin <branch>` | 推送到远程并设置跟踪 |
| `git pull` | 拉取最新代码 |
| `git merge <branch>` | 合并分支 |
| `git branch -d <branch>` | 删除本地分支 |
| `git log --oneline` | 查看简洁版提交日志 |