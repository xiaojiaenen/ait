# ait — AI 智能运维终端 设计文档

> 版本: 0.2.0 | 日期: 2026-05-13

---

## 目录

1. [项目定位](#1-项目定位)
2. [竞品与参考](#2-竞品与参考)
3. [核心功能](#3-核心功能)
4. [TUI 界面设计](#4-tui-界面设计)
5. [技术架构](#5-技术架构)
6. [wuwei 复用策略](#6-wuwei-复用策略)
7. [ait 新增模块](#7-ait-新增模块)
8. [安全模型](#8-安全模型)
9. [Skill 经验沉淀](#9-skill-经验沉淀)
10. [数据流](#10-数据流)
11. [配置体系](#11-配置体系)
12. [开发路线](#12-开发路线)

---

## 1. 项目定位

ait 是一个 **AI 驱动的运维终端**。用户用自然语言描述运维意图，ait 将其转为安全的命令执行，并在过程中沉淀经验为可复用的 Skills。

**一句话**：像和资深同事聊天一样运维服务器，危险操作必须你点头。

**核心原则**：

- **wuwei 能做的，绝对不自己写** —— Agent 运行时、LLM 网关、HITL、Skill、存储、上下文压缩全部复用 wuwei
- **ait 只做运维层** —— SSH 工具、节点管理、危险命令策略、TUI 界面
- **安全不可妥协** —— 所有命令过三级策略，不可逆操作必须人类确认
- **经验自动沉淀** —— 成功的运维操作自动生成 Skill，下次直接复用

---

## 2. 竞品与参考

### 2.1 直接参考（TUI 风格）

| 项目 | 借鉴点 |
|------|--------|
| **Claude Code** | 流式对话 + 侧边栏上下文 + 弹窗审批，简洁克制 |
| **Codex CLI** | 开源 TUI 架构、危险操作二次确认交互 |
| **Warp** | AI 内联建议、分块输出 |

### 2.2 运维参考（功能设计）

| 项目 | 借鉴点 |
|------|--------|
| **Ansible** | Playbook -> Skills 抽象，幂等思想 |
| **Fabric** | SSH 执行的 Pythonic API |
| **K9s** | 运维 TUI 的列表/详情布局 |

### 2.3 差异化

| 维度 | Ansible | Open Interpreter | ait |
|------|---------|-----------------|-----|
| 交互 | YAML 编写 | 自然语言 | 自然语言 + TUI 面板 |
| 多节点 | Y | N | Y |
| 危险确认 | N | N | Y 三级策略 |
| 经验沉淀 | 手动 Playbook | N | Y 自动生成 Skill |
| Agent 框架 | 无 | 自研 | **wuwei（全复用）** |

---

## 3. 核心功能

### 3.1 自然语言运维

```
你> 前端两台机器的 nginx 错误日志最近有什么异常？

ait> 正在检查 web-01、web-02 ...
     [web-01] 最近1小时 500 错误 23 次，主要集中在 /api/order
     [web-02] 最近1小时 500 错误 19 次，同样在 /api/order
     建议查看应用日志中的堆栈信息。
```

### 3.2 多节点 SSH 管理

- 节点配置：host、port、user、key/password、标签
- 分组：`前端` / `后端` / `数据库`，支持标签自由组合
- SSH 连接池（asyncssh），复用连接
- 批量并发执行，结果聚合

### 3.3 三级安全策略

| 级别 | 示例命令 | 行为 |
|------|---------|------|
| **safe** | `ls`, `cat`, `ps`, `df`, `systemctl status` | 自动执行 |
| **confirm** | `systemctl restart`, `kill -9`, `iptables`, `reboot`, `chmod 777`, `docker rm` | **弹窗确认** |
| **block** | `rm -rf /`, `dd if=`, `mkfs`, `chmod -R 777 /` | **直接拒绝** |

```python
# 危险命令规则（正则匹配）
DANGER_RULES = [
    (r"\brm\s+.*-rf\s+/",              "block",   "递归删除根目录"),
    (r"\bdd\s+if=",                     "block",   "磁盘直接写入"),
    (r"\bmkfs\.",                       "block",   "格式化文件系统"),
    (r"\bchmod\s+.*-R\s+777\s+/",       "block",   "递归开放全部权限"),
    (r"\bsystemctl\s+(restart|stop)",   "confirm", "系统服务启停"),
    (r"\bkill\s+-9",                    "confirm", "强制终止进程"),
    (r"\biptables\s+-[ADILF]",          "confirm", "防火墙规则变更"),
    (r"\breboot|shutdown|init\s+[06]",  "confirm", "系统关机/重启"),
    (r"\bdocker\s+(rm|stop|kill)",      "confirm", "容器删除/停止"),
    (r"\bkubectl\s+delete",             "confirm", "K8s 资源删除"),
]
```

### 3.4 经验自动沉淀

执行成功的运维操作，如果涉及 **>=2 个节点** 或 **>=3 个步骤**，Agent 自动总结为 Skill：

```
[OK] 已完成 5 台节点的 nginx 日志切割
[skill] 已沉淀为 Skill: nginx-log-rotation（下次可直接说"切割 nginx 日志"）
```

Skill 格式兼容 wuwei `FileSystemSkillProvider`，存在 `~/.ait/skills/`。

### 3.5 审计日志

- 全量记录：who / when / node / command / result / approved
- 利用 wuwei `FileStorage` 的 jsonl 持久化，自然支持会话回放
- 可导出 Markdown 报告

### 3.6 文件传输

- 上传：本地 -> 远程（单节点或批量分发）
- 下载：远程 -> 本地
- 基于 SSH SFTP（asyncssh 内置）

---

## 4. TUI 界面设计

### 4.1 设计原则

参考 Claude Code / Codex CLI：**简洁、克制、信息密度适中**。

- 不是复杂多面板，而是增强型对话终端
- 默认只显示对话区 + 输入区
- 侧边栏按需展开（节点列表、Skills）
- 危险操作原地弹窗，不跳转

### 4.2 默认布局

```
+----------------------------------------------------------+
| ait . 3 节点在线                         会话: default    |
+----------------------------------------------------------+
|                                                          |
|  +- ait ----------------------------------------------+  |
|  |                                                     |  |
|  |  正在检查 web-01 的 nginx 状态...                    |  |
|  |                                                     |  |
|  |  web-01: nginx active (running) since 3 days        |  |
|  |  web-02: nginx active (running) since 3 days        |  |
|  |                                                     |  |
|  |  两台前端节点的 nginx 均正常运行。                    |  |
|  |                                                     |  |
|  +-----------------------------------------------------+  |
|                                                          |
|  +- [WARNING] 危险操作确认 ---------------------------+  |
|  |  systemctl restart nginx                             |  |
|  |  目标: web-01, web-02 (2 台)                         |  |
|  |  风险: 服务短暂中断                                  |  |
|  |  [ Enter 确认 ]  [ Esc 取消 ]  [ d 查看详情 ]        |  |
|  +-----------------------------------------------------+  |
|                                                          |
|  > 重启前端 nginx                                       |
|                                                          |
+----------------------------------------------------------+
| Tab:补全  Ctrl+N:节点  Ctrl+S:Skills  Ctrl+L:清屏        |
+----------------------------------------------------------+
```

### 4.3 侧边栏（按需展开）

```
+--------------+-----------------------------------+
| 节点 (3/4)    |  对话区                            |
|              |                                   |
| [O] web-01   |  ...                              |
| [O] web-02   |                                   |
| [W] db-01    |                                   |
| [ ] cache-01 |                                   |
|              |                                   |
| [前端]       |                                   |
|  web-01      |                                   |
|  web-02      |                                   |
| [数据库]      |                                   |
|  db-01       |                                   |
|              |                                   |
| Ctrl+N 收起  |                                   |
+--------------+-----------------------------------+
```

### 4.4 配色方案

| 元素 | 颜色 | 用途 |
|------|------|------|
| 在线节点 | 绿色 `#00d700` | 健康 |
| 高负载节点 | 黄色 `#ffd700` | 警告 |
| 离线节点 | 灰色 `#5f5f5f` | 不可达 |
| 危险确认 | 红色 `#ff005f` | 弹窗边框 |
| AI 回复 | 默认前景色 | 主内容 |
| 工具调用 | 紫色 `#5f5faf` | 辅助信息 |

### 4.5 交互快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息 / 确认弹窗 |
| `Shift+Enter` | 换行 |
| `Tab` | 补全节点名/命令/Skill |
| `Ctrl+N` | 展开/收起节点侧边栏 |
| `Ctrl+S` | 展开/收起 Skills 侧边栏 |
| `Ctrl+L` | 清屏 |
| `Ctrl+C` | 退出 |
| `Esc` | 取消弹窗 |
| `UP/DOWN` | 历史消息滚动 / 弹窗选项 |

---

## 5. 技术架构

```
+----------------------------------------------------------+
|                    TUI (Textual)                           |
|  +------------+  +-----------+  +--------------------+   |
|  | ChatScreen |  | NodePanel |  | ConfirmDialog       |   |
|  | (主对话)    |  | (侧边栏)   |  | (危险操作弹窗)       |   |
|  +-----+------+  +-----+-----+  +---------+----------+   |
|        +---------------+---------------+                  |
|                        |                                   |
|              +-----------------+                          |
|              |   OpsAgent      |  <- ait 唯一新增 Agent 层 |
|              | (组装 wuwei +   |                          |
|              |  运维 tools +   |                          |
|              |  安全 hooks)    |                          |
|              +-------+---------+                          |
+----------------------+------------------------------------+
|              +-------+---------+                          |
|              |    wuwei 复用    |  <- 全部来自 wuwei        |
|              |                 |                          |
|              | AgentRunner     |  执行循环                |
|              | LLMGateway      |  LLM 调用                |
|              | ToolRegistry    |  工具注册                |
|              | Context         |  消息管理                |
|              | FileStorage     |  持久化                  |
|              | SkillManager    |  Skill 检索              |
|              |                 |                          |
|              | SkillHook       |  Skill 注入 prompt       |
|              | ContextHook     |  上下文压缩              |
|              | StorageHook     |  消息持久化              |
|              | HitlHook        |  审批拦截 <- ait 注入策略 |
|              | ConsoleHook     |  调试日志                |
|              +-------+---------+                          |
+----------------------+------------------------------------+
|              +-------+---------+                          |
|              |  ait 新增模块    |                          |
|              |                 |                          |
|              | Tools:          |                          |
|              |  exec_command   |  SSH 命令执行             |
|              |  upload/download|  文件传输                 |
|              |  list_nodes     |  节点列表                 |
|              |  monitor        |  指标采集                 |
|              |                 |                          |
|              | Security:       |                          |
|              |  CommandPolicy  |  危险命令策略             |
|              |  TuiApproval    |  TUI 弹窗审批提供者       |
|              |                 |                          |
|              | Nodes:          |                          |
|              |  SSH Pool       |  asyncssh 连接池          |
|              |  NodeManager    |  节点 CRUD               |
|              +-----------------+                          |
+----------------------------------------------------------+
```

---

## 6. wuwei 复用策略

**原则**：wuwei 已有的，一行都不重写。ait 只做运维层。

### 6.1 直接复用的模块

| wuwei 模块 | 在 ait 中的角色 | 复用方式 |
|-----------|---------------|---------|
| `LLMGateway` | LLM 调用入口 | **直接使用**，通过 `from_env()` 读取配置 |
| `Agent` | 单 Agent 运行 | **直接使用** `agent.run()` / `agent.stream_events()` |
| `AgentRunner` | 执行循环 | wuwei Agent 内部自动创建，**不接触** |
| `Context` | 消息上下文 | wuwei AgentSession 内部管理，**不接触** |
| `ToolRegistry` | 工具注册 | **直接使用**，注册运维工具 |
| `ToolExecutor` | 工具执行 | wuwei AgentRunner 内部，**不接触** |
| `FileStorage` | 会话持久化 | **直接使用**，存到 `~/.ait/sessions/` |
| `SkillManager` | Skill 检索 | **直接使用** + `FileSystemSkillProvider` |
| `SkillHook` | Skill 注入 prompt | **直接使用**，无需修改 |
| `ContextCompressionHook` | 长会话压缩 | **直接使用**，配置阈值 |
| `StorageHook` | 消息持久化 | **直接使用**，对接 FileStorage |
| `ConsoleHook` | 调试日志 | **直接使用** 或替换为 TUI 版本 |
| `FileSystemSkillProvider` | Skill 文件加载 | **直接使用**，指向 `~/.ait/skills/` |
| `skill_tools` | list/load/run skill | **直接调用** `register_skill_tools()` |
| `Message / ToolCall / AgentEvent` | 类型定义 | **直接使用** |

### 6.2 扩展使用的模块（继承/实现接口）

| wuwei 接口 | ait 实现 | 作用 |
|-----------|---------|------|
| `ApprovalPolicy` | `DangerousCommandPolicy` | 危险命令判定逻辑 |
| `ApprovalProvider` | `TuiApprovalProvider` | 在 TUI 中弹窗获取确认 |
| `RuntimeHook` | `AuditHook`（可选） | 记录每次命令执行到审计日志 |

### 6.3 LLM 策略

**完全交给 wuwei**。ait 不封装任何 LLM 调用逻辑。

```python
# ait 中唯一与 LLM 相关的代码：把配置传给 wuwei
llm = LLMGateway.from_env(
    api_key=config.llm.api_key,
    base_url=config.llm.base_url,
    model=config.llm.model,
)
```

支持所有 wuwei 兼容的 provider：DeepSeek、OpenAI、Ollama、任何 OpenAI 兼容 API。

---

## 7. ait 新增模块

ait 只在以下 4 个领域新增代码：

### 7.1 TUI（~15% 代码量）

基于 **Textual** 构建，参考 Claude Code 的简洁风格。

```
ait/tui/
├── app.py           # Textual App，组装界面
├── screens/
│   └── chat.py      # 主对话屏幕（唯一默认可见屏幕）
├── widgets/
│   ├── chat_area.py # 对话渲染（Markdown + 流式）
│   ├── input_bar.py # 输入栏（支持多行、补全）
│   ├── confirm.py   # 危险操作确认弹窗
│   ├── node_panel.py # 侧边栏：节点列表（可选展开）
│   └── skill_panel.py # 侧边栏：Skill 列表（可选展开）
└── ait.tcss         # Textual CSS 样式
```

### 7.2 运维 Agent 组装（~10% 代码量）

```python
# ait/agent/ops_agent.py
from wuwei import (
    Agent, LLMGateway, ToolRegistry, FileStorage,
    SkillManager, FileSystemSkillProvider,
    SkillHook, ContextCompressionHook, StorageHook, HitlHook,
)
from wuwei.memory.context_compressor import LLMContextCompressor
from wuwei.tools.builtin.skill_tools import register_skill_tools

class OpsAgent:
    """组装 wuwei 组件 + 运维工具 + 安全策略"""

    def __init__(self, config: AitConfig):
        # LLM - 完全交给 wuwei
        self.llm = LLMGateway.from_env(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
        )

        # Skills - 直接使用 wuwei FileSystemSkillProvider
        self.skill_manager = SkillManager([
            FileSystemSkillProvider(skill_path=config.skills.path)
        ])

        # 工具 - wuwei ToolRegistry + 运维工具
        self.tools = ToolRegistry.from_builtin(["time"])
        register_skill_tools(self.tools, self.skill_manager)
        self._register_ops_tools()  # exec_command, list_nodes 等

        # 存储 - wuwei FileStorage
        self.storage = FileStorage(config.data_dir / "sessions")

        # Hooks - wuwei 全套 + ait 的自定义策略
        self.agent = Agent(
            llm=self.llm,
            tools=self.tools,
            hooks=[
                SkillHook(),
                ContextCompressionHook(
                    compressor=LLMContextCompressor(self.llm),
                    compress_after_turns=30,
                    keep_recent_turns=10,
                ),
                StorageHook(self.storage),
                HitlHook(
                    provider=TuiApprovalProvider(),      # ait 新增
                    policy=DangerousCommandPolicy(),     # ait 新增
                ),
            ],
            default_system_prompt=OPS_SYSTEM_PROMPT,
        )
```

### 7.3 运维工具（~30% 代码量）

注册到 wuwei `ToolRegistry`，Agent 自动调用：

| 工具名 | 描述 | 实现 |
|--------|------|------|
| `exec_command` | 在节点上执行命令 | asyncssh |
| `upload_file` | 上传文件 | SSH SFTP |
| `download_file` | 下载文件 | SSH SFTP |
| `list_nodes` | 列出节点（支持标签筛选） | SQLite 查询 |
| `add_node` | 添加节点 | SQLite 写入 |
| `get_metrics` | 获取节点 CPU/内存/磁盘 | SSH 解析 /proc |

### 7.4 安全模块（~5% 代码量）

```python
# ait/security/policy.py
from wuwei.runtime import ApprovalPolicy

class DangerousCommandPolicy(ApprovalPolicy):
    """继承 wuwei ApprovalPolicy，实现运维命令风险判定"""

    def requires_tool_approval(self, tool_call, *, session, task=None) -> bool:
        # 只对 exec_command 工具做检查
        if tool_call.function.name != "exec_command":
            return False

        command = tool_call.function.arguments.get("command", "")
        for pattern, level, _ in self.rules:
            if re.search(pattern, command):
                if level in ("confirm", "block"):
                    return True
        return False

# ait/security/tui_provider.py
from wuwei.runtime import ApprovalProvider

class TuiApprovalProvider(ApprovalProvider):
    """在 TUI 中弹出确认对话框"""

    async def request_approval(self, request):
        # 通过 Textual 的 Modal 弹窗获取用户决策
        ...
```

### 7.5 节点管理（~20% 代码量）

纯运维逻辑，与 wuwei 无关：

```
ait/nodes/
├── models.py    # Node, Group 数据模型（Pydantic）
├── manager.py   # NodeManager: CRUD + 查询
├── ssh.py       # SSHConnectionPool（基于 asyncssh）
└── monitor.py   # 指标采集（/proc 解析）
```

### 7.6 配置（~5% 代码量）

Pydantic 模型 + TOML 加载。

---

## 8. 安全模型

### 8.1 五层防线

```
用户输入 -> L1 解析 -> L2 策略匹配 -> L3 HITL 审批 -> L4 SSH 执行 -> L5 审计
              |           |             |              |            |
              |     +-----+-----+  +----+----+   +----+----+  +---+---+
              |     | safe      |  | confirm |   | asyncssh|  |jsonl  |
              |     | -> 放行   |  | -> 弹窗  |   | 加密传输|  |追加写入|
              |     | block     |  |         |   |         |  |       |
              |     | -> 拒绝   |  |         |   |         |  |       |
              |     +-----------+  +---------+   +---------+  +-------+
```

### 8.2 复用的 wuwei 安全能力

- **HitlHook**：在 `before_tool` 阶段拦截，调用 `ApprovalProvider`
- **ApprovalPolicy**：决定哪些工具调用需要审批
- **ToolApprovalRejected**：审批被拒时抛出异常，AgentRunner 捕获并反馈给 LLM

ait 只需实现具体策略和 TUI 弹窗。

### 8.3 安全原则

- **零信任**：AI 生成的任何命令都过策略，不假设安全
- **最小权限**：建议被控端使用专用运维账号
- **不可逆必确认**：删除、格式化、重启类始终弹窗
- **全量审计**：无论执行与否，操作意图都记录
- **密码不进文件**：仅支持 SSH key 或每次输入的密码

---

## 9. Skill 经验沉淀

### 9.1 沉淀流程

```
用户任务完成 -> Agent 执行成功
                |
                v
         +--------------+
         | 沉淀判断：     |
         | 步骤>=3 或     |
         | 节点>=2？      |
         +---+----------+
             |是
             v
         Agent 用 LLM 总结操作序列
         -> 生成 SKILL.md（Markdown + YAML frontmatter）
         -> 写入 ~/.ait/skills/<skill-name>/SKILL.md
         -> 通知用户
```

### 9.2 Skill 文件格式

完全兼容 wuwei `FileSystemSkillProvider`：

```markdown
---
name: nginx-log-rotation
description: 批量切割 Nginx 日志文件
tags: [nginx, log, web]
created: 2026-05-13
---

# Nginx 日志切割

## 场景
多节点 Nginx 日志过大需切割归档

## 步骤
1. SSH 到目标节点
2. `df -h /var/log/nginx/` 检查空间
3. `mv access.log access.log.$(date +%Y%m%d)` 重命名
4. `kill -USR1 $(cat /var/run/nginx.pid)` 重新打开日志
5. `ls -lh access.log` 验证

## 回滚
将备份文件改回原名
```

### 9.3 复用的 wuwei Skill 能力

- `FileSystemSkillProvider`：扫描 `SKILL.md` 文件
- `SkillManager`：聚合多个 provider
- `SkillHook`：自动注入 Skill 使用指引到 system prompt
- `list_skills` / `load_skill` / `run_skill_python_script`：内置工具

ait 只需提供目录和维护 Skill 生成逻辑。

---

## 10. 数据流

### 10.1 典型交互

```
用户输入 "前端 nginx 状态怎么样"
  |
  v
OpsAgent.run(user_input)
  |
  v
AgentRunner 执行循环（wuwei 内部）:
  |
  +- SkillHook.before_llm      -> 注入 Skill 指引
  +- ContextHook.before_llm     -> 压缩旧上下文
  +- StorageHook.before_llm     -> 持久化用户消息
  |
  +- LLM 推理 -> tool_calls: [list_nodes, exec_command]
  |
  +- HitlHook.before_tool       -> 检查 exec_command 参数
  |   + 命令是 "systemctl status nginx" -> 安全，放行
  |   + 命令是 "systemctl restart nginx" -> 危险，弹窗
  |
  +- ToolExecutor 执行:
  |   + list_nodes(tags=["前端"]) -> ["web-01", "web-02"]
  |   + exec_command(node="web-01", cmd="systemctl status nginx") -> "active"
  |
  +- StorageHook.after_tool      -> 持久化工具结果
  |
  +- LLM 综合 -> 流式输出 -> TUI 渲染
```

### 10.2 事件流

```
Agent.stream_events() -> AsyncIterator[AgentEvent]
  |
  +- text_delta    -> TUI 追加流式文本
  +- tool_start    -> TUI 显示 "[执行中...]"
  +- tool_end      -> TUI 显示结果摘要
  +- error         -> TUI 显示错误
  +- done          -> TUI 显示 token 统计
```

---

## 11. 配置体系

### 11.1 文件结构

```
~/.ait/
├── config.toml      # 主配置
├── nodes.db         # 节点数据库（SQLite）
├── sessions/        # 会话持久化（wuwei FileStorage）
└── skills/          # 用户 Skills
    ├── nginx-log-rotation/
    │   └── SKILL.md
    └── mysql-backup/
        └── SKILL.md
```

### 11.2 config.toml

```toml
[llm]
api_key = "${DEEPSEEK_API_KEY}"      # 环境变量引用
base_url = "https://api.deepseek.com"
model = "deepseek-chat"

[tui]
theme = "dark"

[nodes]
default_user = "ops"
default_port = 22
key_path = "~/.ssh/id_ed25519"
connect_timeout = 10
command_timeout = 60

[security]
[[security.custom_rules]]
pattern = "kubectl delete ns"
level = "confirm"
description = "删除 K8s 命名空间"

[skills]
auto_generate = true
min_steps = 3
path = "~/.ait/skills"
```

---

## 12. 开发路线

### P0 - 最小可用（单节点对话）

| # | 任务 | 关键复用 |
|---|------|---------|
| 0.1 | 项目骨架、pyproject.toml、依赖 | - |
| 0.2 | CLI 入口 `ait`（typer） | - |
| 0.3 | TUI 框架（Textual App + ChatScreen） | - |
| 0.4 | OpsAgent 组装（wuwei Agent + 运维 prompt） | **wuwei Agent 全部** |
| 0.5 | SSH 连接管理（asyncssh 连接池） | - |
| 0.6 | `exec_command` 工具 | **wuwei ToolRegistry** |
| 0.7 | 危险命令策略 + TUI 确认弹窗 | **wuwei HitlHook + ApprovalPolicy** |
| 0.8 | 会话持久化 + 审计 | **wuwei FileStorage + StorageHook** |
| 0.9 | 配置文件管理 | - |

### P1 - 多节点

| # | 任务 | 关键复用 |
|---|------|---------|
| 1.1 | 节点列表侧边栏 | - |
| 1.2 | 节点分组 | - |
| 1.3 | 批量执行 + 结果聚合 | - |
| 1.4 | 文件上传/下载 | - |

### P2 - Skills

| # | 任务 | 关键复用 |
|---|------|---------|
| 2.1 | Skill 侧边栏 | **wuwei SkillManager + FileSystemSkillProvider** |
| 2.2 | 自动沉淀（Agent 总结 -> SKILL.md） | **wuwei SkillHook** |
| 2.3 | 对话中自动推荐 Skill | **wuwei skill_tools** |

### P3 - 监控与增强

| # | 任务 |
|---|------|
| 3.1 | 实时监控指标采集 |
| 3.2 | 阈值告警（侧边栏变色） |
| 3.3 | 会话回放 |
| 3.4 | 快捷宏 / 别名 |

---

## 附录 A: 依赖清单

```toml
[project]
name = "ait"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "wuwei>=0.1.8",             # Agent 框架（Agent/LLM/HITL/Skill/Storage/Hooks）
    "textual>=2.1.0",           # TUI 框架
    "asyncssh>=2.19.0",         # SSH 异步客户端
    "pydantic>=2.10.0",         # 数据模型（wuwei 已依赖，ait 也用）
    "typer>=0.15.0",            # CLI 入口
    "python-dotenv>=1.1.0",     # .env 加载
    "structlog>=25.0.0",        # 结构化日志
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
    "ruff>=0.11.0",
]
```

### 依赖说明

| 依赖 | 为什么需要 | 能否去掉 |
|------|-----------|---------|
| `wuwei` | Agent 运行时、LLM、HITL、Skill、存储 | X 核心 |
| `textual` | TUI 界面渲染 | X 核心 |
| `asyncssh` | SSH 连接和命令执行 | X 核心 |
| `pydantic` | 配置/节点模型校验 | X wuwei 已依赖 |
| `typer` | CLI 入口（`ait` 命令） | 可用 argparse 替代 |
| `python-dotenv` | API key 管理 | 可手动 export |
| `structlog` | 审计日志结构化 | 可用 logging 替代 |

---

## 附录 B: 目录结构

```
~/code/ait/
├── ait/
│   ├── __init__.py
│   ├── app.py              # Textual App 主入口
│   ├── cli.py              # CLI 入口（typer）
│   ├── config.py           # 配置模型 + TOML 加载
│   ├── ait.tcss            # Textual 样式
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── screens/
│   │   │   └── chat.py     # 主对话屏幕
│   │   └── widgets/
│   │       ├── __init__.py
│   │       ├── chat_area.py    # 对话渲染
│   │       ├── input_bar.py    # 输入栏
│   │       ├── confirm.py      # 危险确认弹窗
│   │       ├── node_panel.py   # 节点侧边栏
│   │       └── skill_panel.py  # Skill 侧边栏
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── ops_agent.py    # 运维 Agent（组装 wuwei + 运维层）
│   │   └── prompts.py      # 运维专用 system prompt
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── models.py       # Node/Group Pydantic 模型
│   │   ├── manager.py      # 节点 CRUD
│   │   ├── ssh.py          # SSH 连接池
│   │   └── monitor.py      # 指标采集
│   ├── security/
│   │   ├── __init__.py
│   │   ├── policy.py       # DangerousCommandPolicy
│   │   └── tui_provider.py # TuiApprovalProvider
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── ssh_tools.py    # exec_command / upload / download
│   │   ├── node_tools.py   # list_nodes / add_node
│   │   └── monitor_tools.py
│   └── skills/
│       ├── __init__.py
│       └── generator.py    # Skill 自动生成
├── docs/
│   └── DESIGN.md           # 本文档
├── tests/
│   └── __init__.py
├── pyproject.toml
├── .gitignore
└── README.md
```

---

## 附录 C: 与上一版的变更

| 变更项 | 0.1.0 | 0.2.0 |
|--------|-------|-------|
| TUI 设计 | 多面板固定布局 | 简洁对话为主，侧边栏可选展开 |
| LLM 接入 | 列表对比 provider | **全部交给 wuwei LLMGateway** |
| 存储 | SQLAlchemy + JSONL | **直接复用 wuwei FileStorage** |
| Agent 层 | 较厚的封装 | **薄封装，只做组装** |
| 审计 | 自建 SQLite | **复用 wuwei StorageHook + jsonl** |
| 依赖 | aiosqlite 等额外依赖 | 精简到 7 个核心依赖 |
| Python | >=3.10 | >=3.11（支持 tomllib） |
