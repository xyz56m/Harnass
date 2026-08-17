# DeepSeek Harness for Android — 增强版

> 🚀 **在 Android 手机上原生运行 DeepSeek Harness，配备 16 个 MCP 服务器、前沿论文编码技术、自循环工作流**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android/Termux-3DDC84)](https://termux.com)
[![DSH Version](https://img.shields.io/badge/dsh-0.1.0--rc.6-blue)](https://github.com/deepseek-ai/deepseek-harness)
[![MCP Servers](https://img.shields.io/badge/MCP-16%20servers-8A2BE2)](config/mcp.cordis.patch.yml)
[![Presets](https://img.shields.io/badge/presets-3%20modes-FF6B6B)](config/)

---

**中文** · [English](#english)

---

## 📋 目录

- [项目简介](#项目简介)
- [核心功能](#核心功能)
- [与官方 Harness 对比](#与官方-harness-对比)
- [快速开始](#快速开始)
- [预设模式](#预设模式)
- [MCP 服务器列表](#mcp-服务器列表)
- [前沿技术](#前沿技术)
- [项目结构](#项目结构)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 项目简介

本项目是 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`@deepseek-ai/dsh`，DeepSeek 官方的 agent harness，类 Claude Code）在 **Android/Termux** 环境的一键部署增强版。

在官方一键部署脚本的基础上，本项目增加了：

- **16 个开箱即用的 MCP 服务器**（官方 0 个）
- **3 个预设模式**：编码模式 (Android)、DeepSearch 编码模式、以及官方全部预设
- **前沿论文编码技术**：Reflexion、Self-Refine、Self-Debugging、AlphaCodium
- **六阶段自循环工作流**：分析需求 → 计划 → 研究 → 执行 → 验证 → 迭代
- **自进化机制**：反思 → 记录 → 调整 → 验证 → 固化
- **自动代码分析**：复杂度检查、安全扫描、自动修复建议
- **风神插件**：官方 AGENTS.md + 11 个 Skills + Agent Notes
- **活动记忆**：跨会话持久化用户偏好、编码习惯、项目上下文
- **第三方 API 兼容**：OpenAI、Anthropic、OpenRouter 等

---

## 核心功能

### 🤖 智能编码代理
- 基于 DeepSeek Harness 官方引擎，支持 bash、文件系统、子代理、工作流
- **Code Mode**（PTC）：多步操作打包为一次 TypeScript 程序执行，减少往返与 token 消耗
- **六阶段自循环**：自动执行分析→计划→研究→执行→验证→迭代

### 🧩 16 个 MCP 服务器
| 分类 | 服务器 |
|------|--------|
| 编码与代码 | code_quality（5 个分析工具）、diff |
| 搜索与信息 | brave_search、youtube、weather |
| 文件与存储 | filesystem、sqlite、markdown |
| 图像与媒体 | vision（OCR 识图）、media（图片处理）、qrcode |
| 记忆与知识 | memory（知识图谱）、activity_memory（活动记忆） |
| 开发工具 | github（需 token）、sequential_thinking（结构化推理） |
| 实用工具 | utils（uuid/hash/base64/regex/emoji/翻译，共 11 个工具） |
| 协议测试 | everything（MCP 协议测试） |

### 📚 前沿论文驱动的编码质量
- **Reflexion**（NeurIPS 2023）：反思强化学习，从错误中学习
- **Self-Refine**（2023）：自优化循环，生成→反馈→改进
- **Self-Debugging**（2024）：自调试，解释→执行→分析→修复
- **AlphaCodium**（2024）：迭代生成，先写测试→生成代码→修复

### 🔄 自进化机制
- 每次任务后自动反思，记录经验到活动记忆
- 跨会话积累编码习惯、项目上下文、学习记录
- 遇错立即记录，越用越聪明

### 📱 移动端优化
- 专为 Android 竖屏优化的 Web UI
- 代码块横向滚动 + 一键复制
- 触控目标 ≥ 44px
- 输入法回车→换行，Ctrl+Enter→发送
- 资源感知：避免手机 OOM

---

## 与官方 Harness 对比

| 能力 | 官方 Harness | 本项目 |
|------|:----------:|:------:|
| **MCP 服务器** | 0 | **16**（含 11 工具实用集） |
| **预设模式** | 4（标准/PTC/创造/极简） | **6**（含 2 个增强模式） |
| **自循环工作流** | ❌ | ✅ **六阶段** |
| **自进化机制** | ❌ | ✅ |
| **前沿论文技术** | ❌ | ✅ **4 篇论文实现** |
| **自动代码分析** | ❌ | ✅ **5 个分析工具** |
| **活动记忆** | ❌ | ✅ **跨会话持久化** |
| **风神插件** | ❌ | ✅ **AGENTS.md + 11 Skills** |
| **第三方 API 兼容** | ❌ | ✅ **OpenAI/Anthropic/OpenRouter** |
| **移动端适配** | ❌ | ✅ **竖屏 + 触控 + 代码块** |
| **总能力** | 19 项 | **34 项**（+79%） |

---

## 快速开始

### 前置要求

- Android 手机
- [Termux](https://f-droid.org/en/packages/com.termux/)（F-Droid 版，**不要用 Google Play 版**）

### 一键安装

```bash
pkg install -y git
git clone https://github.com/xyz56m/Harnass.git
cd Harnass
bash setup.sh
```

> 🇨🇳 国内用户：`setup.sh` 会自动测速，npm 源慢时自动切换到 npmmirror 镜像。

### 使用

```bash
bash ~/dsh/start_dsh.sh   # 启动
bash ~/dsh/stop_dsh.sh    # 停止
```

打开 http://127.0.0.1:3080，在 Models 页面填入 DeepSeek API Key，在预设选择中切换模式。

---

## 预设模式

安装后，在 Web UI 的预设选择中可选：

| 预设 | 基座 | 适用场景 |
|------|------|----------|
| **编码模式 (Android)** 🏆 | cordis（创造模式） | **日常编码首选**：六阶段自循环 + Code Mode + 自修改 + 16 MCP |
| **DeepSearch 编码模式** 🆕 | cordis（创造模式） | **深度研究编码**：先联网搜索研究再自动编码 + 全流程验证 |
| 标准模式 | standard | 官方标准模式 |
| PTC 模式 | code | 官方 PTC/Code Mode |
| 创造模式 | cordis | 官方创造模式（自修改） |
| 极简模式 | minimal | 官方极简模式 |

---

## MCP 服务器列表

| 服务器 | 包名 | 工具前缀 | 功能 |
|--------|------|----------|------|
| `github` | `@modelcontextprotocol/server-github` | `mcp__github__*` | GitHub API（需 GITHUB_TOKEN） |
| `filesystem` | `@modelcontextprotocol/server-filesystem` | `mcp__filesystem__*` | 结构化文件系统访问 |
| `memory` | `@modelcontextprotocol/server-memory` | `mcp__memory__*` | 知识图谱记忆 |
| `sequential_thinking` | `@modelcontextprotocol/server-sequential-thinking` | `mcp__sequential_thinking__*` | 结构化推理 |
| `everything` | `@modelcontextprotocol/server-everything` | `mcp__everything__*` | MCP 协议测试 |
| `brave_search` | `@modelcontextprotocol/server-brave-search` | `mcp__brave_search__*` | 联网搜索 |
| `vision` | 自定义 Python | `mcp__vision__*` | OCR 文字识别 + 图片元信息 |
| `media` | 自定义 Python | `mcp__media__*` | 图片格式转换/缩放/压缩 |
| `qrcode` | `mcp-server-qrcode` | `mcp__qrcode__*` | QR 码生成 |
| `activity_memory` | 自定义 Python | `mcp__activity_memory__*` | 活动记忆（跨会话） |
| `code_quality` | 自定义 Python | `mcp__code_quality__*` | 代码质量分析（5 个工具） |
| `sqlite` | `mcp-server-sqlite` | `mcp__sqlite__*` | SQLite 数据库操作 |
| `markdown` | `mcp-server-markdown` | `mcp__markdown__*` | Markdown 文档处理 |
| `utils` | 自定义 Python | `mcp__utils__*` | **11 个工具**：uuid/hash/base64/regex/emoji/翻译 |
| `diff` | `mcp-server-diff` | `mcp__diff__*` | 差异对比 |
| `weather` | `mcp-server-weather` | `mcp__weather__*` | 天气查询 |
| `youtube` | `mcp-server-youtube` | `mcp__youtube__*` | YouTube 视频搜索 |

> 所有 MCP 服务器配置在 `~/.dsh/profiles/web/cordis.patch.yml`，可手动编辑增删。

---

## 前沿技术

### 论文实现

| 论文 | 年份 | 会议 | 核心思想 | 实现方式 |
|------|------|------|----------|----------|
| [Reflexion](https://arxiv.org/abs/2303.11366) | 2023 | NeurIPS | 反思强化学习：用语言反馈信号替代梯度更新 | activity_memory 存储经验 + self-evolution 循环 |
| [Self-Refine](https://arxiv.org/abs/2303.17651) | 2023 | — | 自优化：Generate → Feedback → Refine | plan mode 内嵌自优化流程 |
| [Self-Debugging](https://arxiv.org/abs/2304.05128) | 2024 | — | 自调试：Explain → Execute → Debug | plan mode VERIFY 阶段升级 |
| [AlphaCodium](https://codium.ai/) | 2024 | — | 迭代生成：先写测试→生成代码→修复 | plan mode ITERATE 阶段加入 |

### 自动代码分析

| 工具 | 功能 |
|------|------|
| `analyze_code` | 单文件深度分析（复杂度、安全、风格、最佳实践） |
| `analyze_directory` | 目录质量概览对比 |
| `auto_analyze` | 自动扫描最近修改文件（每个变更后自动触发） |
| `git_diff_analyze` | git diff 安全分析（提交前自动触发） |
| `auto_fix_suggest` | 自动生成修复建议 |

---

## 项目结构

```
Harnass/
├── setup.sh                 # 一键安装脚本（10 步）
├── config/
│   ├── mcp.cordis.patch.yml # 16 个 MCP 服务器配置
│   ├── android-code/        # 编码模式 (Android) 预设
│   └── deepsearch-coding/   # DeepSearch 编码模式预设
├── scripts/
│   ├── vision-mcp.py        # OCR 识图 MCP 服务器
│   ├── media-mcp.py         # 图片处理 MCP 服务器
│   ├── activity-memory-mcp.py # 活动记忆 MCP 服务器
│   ├── code-quality-mcp.py  # 代码质量分析 MCP 服务器
│   └── utils-mcp.py         # 实用工具 MCP 服务器（11 个工具，零外部依赖）
├── patches/
│   ├── mobile.css/js        # 移动端适配
│   └── *.patch              # JS 性能补丁（历史瘦身/增量同步/缓存）
├── .agents/                 # 风神插件（官方 AGENTS.md + Skills + Notes）
├── docs/
│   └── index.html           # 项目文档页
├── start_dsh.sh             # 启动脚本
├── stop_dsh.sh              # 停止脚本
└── apply-frontend.sh        # 前端适配脚本
```

---

## 常见问题

### 安装报错
- **koffi 编译失败（`spawn.h` 未找到）**：`pkg install ndk-sysroot`，然后重跑 setup.sh
- **npm install 失败**：`npm i -g npm` 升级 npm，然后重跑 setup.sh
- **MCP 服务器没出现**：检查 `~/dsh/storage/dsh.log`，确认包已安装

### 使用问题
- **页面白屏**：确认在 Termux 环境，看 `~/dsh/storage/dsh.log`
- **模型没反应**：检查 Models 页 API Key 与 `~/.dsh/.credentials.yaml`
- **浏览器报错**：
  - `AbortSignal.any is not a function`：浏览器过旧，`apply-frontend.sh` 已注入 polyfill
  - `crypto.randomUUID is not a function`：局域网 HTTP，`apply-frontend.sh` 已注入回退

---

## 贡献指南

欢迎贡献！你可以：

1. **提交 Issue**：报告 bug 或建议新功能
2. **提交 Pull Request**：修复问题或添加新 MCP 服务器
3. **适配新机型**：在不同 Android 版本/ROM 上测试并报告兼容性

### 开发指南

```bash
# 本地测试
bash -n setup.sh  # 语法检查
python3 -c "import py_compile; py_compile.compile('scripts/vision-mcp.py', doraise=True)"

# 添加新 MCP 服务器
# 1. 在 config/mcp.cordis.patch.yml 添加配置
# 2. 在 setup.sh 的 MCP 安装列表添加包名
# 3. 更新 README.md 和 docs/index.html
```

---

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)

---

## 致谢

- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) — DeepSeek 官方 agent harness
- [Termux](https://termux.com/) — Android 终端模拟器
- [Model Context Protocol](https://modelcontextprotocol.io/) — MCP 协议
- [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) — 社区 MCP 服务器列表

---

<div id="english"></div>

## English

> **DeepSeek Harness Enhanced for Android/Termux**

One-click deployment of DeepSeek Harness on Android with **23 MCP servers**, **cutting-edge paper-driven coding techniques**, and **6-stage self-loop workflow**.

### Key Features

- **16 MCP servers** out of the box (GitHub, Filesystem, Vision OCR, Media Processing, Code Quality, SQLite, Brave Search, Sequential Thinking, Utils with 11 tools, etc.)
- **3 custom presets**: Android Coding Mode, DeepSearch Coding Mode
- **Paper-driven coding quality**: Reflexion, Self-Refine, Self-Debugging, AlphaCodium
- **6-stage self-loop**: Analyze → Plan → Research → Execute → Verify → Iterate
- **Self-evolution**: Reflect → Record → Adapt → Verify → Solidify
- **Auto code analysis**: complexity, security scan, auto-fix suggestions
- **Fengshen Plugin**: Official AGENTS.md + 11 Skills + Agent Notes
- **Activity memory**: cross-session persistent memory
- **Third-party API support**: OpenAI, Anthropic, OpenRouter
- **Mobile-optimized UI**: vertical screen, touch targets, scrollable code blocks

### Quick Start

```bash
pkg install -y git
git clone https://github.com/xyz56m/Harnass.git
cd Harnass
bash setup.sh
bash ~/dsh/start_dsh.sh
```

### Comparison with Official Harness

| Feature | Official | This Project |
|---------|:--------:|:------------:|
| MCP Servers | 0 | **23** |
| Custom Presets | 0 | **2** |
| Self-Loop Workflow | ❌ | ✅ **6-stage** |
| Paper-Driven Tech | ❌ | ✅ **4 papers** |
| Auto Code Analysis | ❌ | ✅ **5 tools** |
| Activity Memory | ❌ | ✅ |
| Fengshen Plugin | ❌ | ✅ |
| Total Capabilities | 19 | **34 (+79%)** |