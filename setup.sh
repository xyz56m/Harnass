#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# DeepSeek Harness (dsh) 一键安装脚本 — Android / Termux
# -----------------------------------------------------------------------------
# 安装 DeepSeek 官方 agent harness (@deepseek-ai/dsh) 并在 Termux 上跑起来，
# 自动完成所有 Android 兼容修复：
#   1. 检查/安装构建依赖 (cmake/clang/make/binutils/pkg-config/python/nodejs/ndk-sysroot)
#   2. 准备 node-gyp 缓存 → 修补 common.gypi（修 node-pty 构建）
#   3. 用 android30 编译目标安装 dsh（修 koffi statx）+ 放行构建脚本
#   4. 修补 link() → rename()、subprocess 终端检测、回车键行为
#   5. 安装 sharp WebAssembly 回退（android-arm64 无原生预编译）
#   6. 重建 /usr/bin/dsh 包装脚本（--expose-internals，HMR 必需）
#   7. 写入启动/停止脚本 + 权限模式配置
#   8. 安装 MCP 服务器（GitHub / Filesystem / Vision OCR / Media / QR / Memory / Activity Memory）并写入 profile 配置
#   9. 安装 Android 编码增强预设（基于官方 cordis 创造模式 + Code Mode + 风神插件 + 任务分解 + MCP 工具链）
#  10. 应用前端移动端适配 + JS 性能补丁
#
# 用法：
#   bash setup.sh
# 之后：
#   bash ~/dsh/start_dsh.sh     # 启动并拉起 Chrome
#   在 Web UI (http://127.0.0.1:3080) 的 Models 页配置 DeepSeek API Key
# =============================================================================
set -euo pipefail

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[v]\033[0m %s\n' "$*"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"   # 脚本真实目录（脚本中段会 cd，须用绝对路径）
DSH_NPM="@deepseek-ai/dsh"
DSH_DIR="/data/data/com.termux/files/usr/lib/node_modules/@deepseek-ai/dsh"
INSTALL_DIR="$HOME/dsh"

# ---------------------------------------------------------------- 1/10 依赖
info "1/10 检查构建依赖 (cmake clang make binutils pkg-config python nodejs)"
# 幂等：检查关键命令是否已存在，缺失的才安装（已手动装过则直接跳过）
MISSING_DEPS=""
for dep in node npm python3 cmake clang make pkg-config; do
  command -v "$dep" >/dev/null 2>&1 || MISSING_DEPS="$MISSING_DEPS $dep"
done
if [ -n "$MISSING_DEPS" ]; then
  warn "缺少依赖:${MISSING_DEPS}，开始安装（已装的自动跳过）..."
  pkg update -y >/dev/null 2>&1 || true
  pkg install -y cmake clang make binutils pkg-config python nodejs ndk-sysroot >/dev/null 2>&1 || true
  # 二次确认
  for dep in node npm python3 cmake clang make pkg-config; do
    command -v "$dep" >/dev/null 2>&1 && ok "  $dep 就绪" || warn "  $dep 仍缺失"
  done
else
  ok "  构建依赖已全部就绪，跳过安装"
fi

command -v node >/dev/null 2>&1 || { warn "node 未安装，重试安装 nodejs..."; pkg install -y nodejs; }
NODE_VER="$(node -v 2>/dev/null | sed 's/^v//' || echo 'unknown')"
info "Node.js v${NODE_VER}"

# --------------------------------------------------- 智能换源（国内用户友好）
# 检测默认 npm / nodejs.org 是否太慢，慢则自动切换到 npmmirror 镜像。
# 仅通过环境变量作用于本次安装会话，不改动全局 npm 配置。
is_slow() {
  local url="$1" t
  t=$(curl -o /dev/null -s -w '%{time_total}' --max-time 6 "$url" 2>/dev/null)
  [ -z "$t" ] && return 0
  awk -v t="$t" 'BEGIN { exit !(t > 1.0) }'
}
if is_slow "https://registry.npmjs.org/-/ping"; then
  info "默认 npm 源较慢，自动切换到 npmmirror 镜像 (registry.npmmirror.com)"
  export npm_config_registry="https://registry.npmmirror.com"
fi
if is_slow "https://nodejs.org/dist/"; then
  info "nodejs.org 较慢，node-gyp 下载 Node headers 自动切换到 npmmirror 镜像"
  export npm_config_disturl="https://npmmirror.com/mirrors/node/"
fi

# ------------------------------------------------------- 2/10 准备 gyp 补丁
info "2/10 准备 node-gyp 缓存（已存在则跳过）"
# node-gyp 首次构建会把 node headers 解压到缓存，其中 common.gypi 引用了
# android_ndk_path 变量；Termux 无 NDK 该变量未定义 → 必须修补缓存文件。
# 这里用 `node-gyp install` 只下载 headers（远快于整树 npm install），随后打补丁。
# 若此处卡住：多为网络问题，检查能否访问 nodejs.org；超时 300s 后自动跳过并告警。
GYP_GIPI="$HOME/.cache/node-gyp/$NODE_VER/include/node/common.gypi"
if [ -f "$GYP_GIPI" ] && grep -q "android_ndk_path" "$GYP_GIPI" 2>/dev/null; then
  ok "  node-gyp 缓存已就绪且已修补，跳过"
else
  if [ -f "$GYP_GIPI" ]; then
    info "  common.gypi 已存在但未修补，直接修补..."
  else
    info "  下载 Node headers 填充 node-gyp 缓存（约 1 分钟，请稍候）..."
    timeout 300 npx --yes node-gyp install 2>&1 | tail -3 || true
  fi
  if [ -f "$GYP_GIPI" ]; then
    info "修补 common.gypi: 定义 android_ndk_path 为空（修 node-pty 的 Undefined variable 错误）"
    python3 - "$GYP_GIPI" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
if "'android_ndk_path%': ''" not in s:
    s = s.replace("'variables': {", "'variables': {\n    'android_ndk_path%': '',", 1)
    open(p, 'w', encoding='utf-8').write(s)
print("  patched common.gypi")
PY
  else
    warn "未找到 $GYP_GIPI，请确认 node 已安装；可先手动跑一次 `npm i -g @deepseek-ai/dsh` 填充缓存"
  fi
fi

# ------------------------------------------------------------- 3/10 正式安装
info "3/10 用 android30 编译目标正式安装 dsh（下载依赖+原生编译，可能需要 5~15 分钟，请耐心等待，不要中断）"

# 检测 npm 版本，适配 --allow-scripts 参数（npm 11+ 才支持）
NPM_VER="$(npm --version 2>/dev/null | cut -d. -f1 || echo 0)"
NPM_ALLOW_SCRIPTS=""
if [ "$NPM_VER" -ge 11 ] 2>/dev/null; then
  NPM_ALLOW_SCRIPTS="--allow-scripts=@deepseek-ai/dsh-subprocess-local,koffi,node-pty,@google/genai,protobufjs"
  info "  npm v${NPM_VER}，启用 --allow-scripts 放行原生编译"
else
  info "  npm v${NPM_VER}，较旧版本不支持 --allow-scripts，使用 --ignore-scripts + 手动编译"
  NPM_ALLOW_SCRIPTS=""
fi

CFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" CXXFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" \
  npm install -g ${NPM_ALLOW_SCRIPTS} "$DSH_NPM" || {
    warn "dsh 首次安装失败，重试一次（网络/编译偶发问题可自愈）..."
    CFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" CXXFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" \
      npm install -g ${NPM_ALLOW_SCRIPTS} "$DSH_NPM"
  }

# 检查原生编译产物
if [ -f "$DSH_DIR/node_modules/node-pty/build/Release/pty.node" ]; then
  ok "node-pty 编译产物就位"
else
  warn "node-pty 未编译（Android 常见兼容问题），尝试手动编译..."
  cd "$DSH_DIR/node_modules/node-pty" && CFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" CXXFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" node-gyp rebuild 2>/dev/null || true
  test -f "$DSH_DIR/node_modules/node-pty/build/Release/pty.node" && ok "  node-pty 手动编译成功" || warn "  node-pty 编译失败，部分功能可能受限"
fi

if [ -f "$DSH_DIR/node_modules/koffi/build/koffi/android_arm64/koffi.node" ]; then
  ok "koffi 编译产物就位"
else
  warn "koffi 未编译，尝试手动编译..."
  cd "$DSH_DIR/node_modules/koffi" && CFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" CXXFLAGS="-target aarch64-linux-android30 -D__ANDROID_API__=30" node ./cnoke.cjs -P . -D src/koffi --prebuild --release 2>/dev/null || true
  test -f "$DSH_DIR/node_modules/koffi/build/koffi/android_arm64/koffi.node" && ok "  koffi 手动编译成功" || warn "  koffi 编译失败，部分功能可能受限"
fi

# ------------------------------------------------------- 4/10 后端兼容补丁
info "4/10 后端兼容补丁"

# 4a: 会话持久化 link→rename（Android 禁 hardlink）
SJ="$DSH_DIR/node_modules/@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js"
if grep -q "rename(tmp, finalPath)" "$SJ" 2>/dev/null; then
  ok "  session-persistence 已修补"
else
  python3 - "$SJ" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
s = s.replace('import { link, mkdir,', 'import { mkdir,')
s = s.replace('realpath, rm,', 'realpath, rename, rm,')
s = s.replace('await link(tmp, finalPath);', 'await rename(tmp, finalPath);')
open(p, 'w', encoding='utf-8').write(s)
print("  patched session-persistence-jsonl (link→rename)")
PY
fi

# 4b: 附件存储 link→rename
AL="$DSH_DIR/node_modules/@deepseek-ai/dsh-attachment-local/lib/index.js"
if grep -q "rename(temporary, target)" "$AL" 2>/dev/null; then
  ok "  attachment-local 已修补"
else
  python3 - "$AL" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
s = s.replace('import { chmod, link, mkdir,', 'import { chmod, mkdir,')
s = s.replace('readFile, unlink }', 'readFile, rename, unlink }')
s = s.replace('await link(temporary, target);', 'await rename(temporary, target);')
open(p, 'w', encoding='utf-8').write(s)
print("  patched attachment-local (link→rename)")
PY
fi

# 4c: subprocess 终端检测 android 视同 linux
SP="$DSH_DIR/node_modules/@deepseek-ai/dsh-subprocess-local/lib/index.js"
if grep -q 'platform === "android"' "$SP" 2>/dev/null; then
  ok "  subprocess-local 已修补"
else
  python3 - "$SP" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
s = s.replace(
  'if (platform === "linux") return new LinuxProcessInspector(arch, internals);',
  'if (platform === "linux" || platform === "android") return new LinuxProcessInspector(arch, internals);')
open(p, 'w', encoding='utf-8').write(s)
print("  patched subprocess-local (android→linux)")
PY
fi

# 4d: 作曲栏 普通回车=换行（不发送），Ctrl/Cmd+Enter=发送
# 安卓输入法/键盘的回车会误触发发送，改为在 React 处理里对非加速回车
# 提前 return（textarea 默认行为=换行）。对应 apply-frontend.sh 注入的
# enterkeyhint=newline（让输入法回车键显示"换行"）。
CB="$DSH_DIR/node_modules/@deepseek-ai/dsh-client-ui-conversation/lib/client.js"
if grep -q "dsh-android: 普通回车换行" "$CB" 2>/dev/null; then
  ok "  client-ui-conversation 回车补丁已就位"
else
  python3 - "$CB" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
old = (
  '\t\t\t\tif (keyboard.arbitrate("enter", composing) !== "pass") {\n'
  '\t\t\t\t\te.preventDefault();\n'
  '\t\t\t\t\treturn;\n'
  '\t\t\t\t}\n'
  '\t\t\t\te.preventDefault();\n'
  '\t\t\t\tif (e.repeat) return;\n'
  '\t\t\t\tif (locked || machineBusy) return;\n'
  '\t\t\t\tconst accelerated = e.ctrlKey || e.metaKey;\n'
  '\t\t\t\tif (accelerated && canSteerQueue) {\n'
  '\t\t\t\t\tkeyboard.steerQueue();\n'
  '\t\t\t\t\treturn;\n'
  '\t\t\t\t}\n'
  '\t\t\t\tkeyboard.submit(resolveSubmitMode(running, accelerated ? "accelerated" : "enter", subagent === null));\n'
)
new = (
  '\t\t\t\tif (keyboard.arbitrate("enter", composing) !== "pass") {\n'
  '\t\t\t\t\te.preventDefault();\n'
  '\t\t\t\t\treturn;\n'
  '\t\t\t\t}\n'
  '\t\t\t\tconst accelerated = e.ctrlKey || e.metaKey;\n'
  '\t\t\t\tif (!accelerated) return; /* dsh-android: 普通回车换行，Ctrl/Cmd+Enter 发送 */\n'
  '\t\t\t\te.preventDefault();\n'
  '\t\t\t\tif (e.repeat) return;\n'
  '\t\t\t\tif (locked || machineBusy) return;\n'
  '\t\t\t\tif (accelerated && canSteerQueue) {\n'
  '\t\t\t\t\tkeyboard.steerQueue();\n'
  '\t\t\t\t\treturn;\n'
  '\t\t\t\t}\n'
  '\t\t\t\tkeyboard.submit(resolveSubmitMode(running, "accelerated", subagent === null));\n'
)
if s.count(old) != 1:
  print("  WARN: 回车补丁模式未精确匹配，跳过（请人工检查）")
  sys.exit(0)
open(p, 'w', encoding='utf-8').write(s.replace(old, new))
print("  patched client-ui-conversation (Enter=newline, Ctrl+Enter=send)")
PY
fi

# ------------------------------------------------------ 5/10 sharp wasm 回退
info "5/10 安装 sharp WebAssembly 回退（android-arm64 无原生预编译）"
SHARP_VER="$(node -e "console.log(require('$DSH_DIR/node_modules/sharp/package.json').version)" 2>/dev/null || echo 0.35.3)"
if [ -d "$DSH_DIR/node_modules/@img/sharp-wasm32" ]; then
  ok "  sharp-wasm32 已就位 (v${SHARP_VER})"
else
  SWTMP="$(mktemp -d)"
  cd "$SWTMP"
  npm init -y >/dev/null 2>&1
  npm install "@img/sharp-wasm32@$SHARP_VER" >/dev/null 2>&1
  mkdir -p "$DSH_DIR/node_modules/@img"
  cp -r node_modules/@img/sharp-wasm32 "$DSH_DIR/node_modules/@img/"
  cp -r node_modules/@emnapi "$DSH_DIR/node_modules/" 2>/dev/null || true
  cd "$HOME"
  rm -rf "$SWTMP"
  ok "  sharp-wasm32@${SHARP_VER} 已安装"
fi

# ------------------------------------------------------ 6/10 dsh 包装脚本
info "6/10 重建 /usr/bin/dsh 包装脚本（--expose-internals，HMR 必需）"
rm -f /data/data/com.termux/files/usr/bin/dsh
cat > /data/data/com.termux/files/usr/bin/dsh <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec node --expose-internals /data/data/com.termux/files/usr/lib/node_modules/@deepseek-ai/dsh/lib/bin.js "$@"
EOF
chmod +x /data/data/com.termux/files/usr/bin/dsh
dsh --version && ok "dsh $(dsh --version) 可用"

# ----------------------------------------------------- 7/10 启动/停止脚本
info "7/10 写入启动/停止脚本到 $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/storage"
cp "$SCRIPT_DIR/start_dsh.sh" "$INSTALL_DIR/start_dsh.sh"
cp "$SCRIPT_DIR/stop_dsh.sh"  "$INSTALL_DIR/stop_dsh.sh"
chmod +x "$INSTALL_DIR/start_dsh.sh" "$INSTALL_DIR/stop_dsh.sh"

# 权限模式：Android 上 bwrap/landlock 命名空间沙箱不可用，bash 工具需
# danger-full-access 才能执行。写入 profile 配置层 + 启动脚本环境变量双保险。
PROFILE_PATCH="$HOME/.dsh/profiles/web/cordis.patch.yml"
mkdir -p "$(dirname "$PROFILE_PATCH")"
if ! grep -q "danger-full-access" "$PROFILE_PATCH" 2>/dev/null; then
  cat > "$PROFILE_PATCH" <<'YAML'
# Android/Termux：bwrap/landlock 命名空间沙箱不可用，需放开权限模式才能执行 bash 工具
- id: sandbox-policy
  config:
    mode: danger-full-access
YAML
  ok "  权限模式已写入 $PROFILE_PATCH"
fi

# ------------------------------------------------- 8/10 MCP 服务器（可选）
info "8/10 安装 MCP 服务器（23 个社区 MCP 服务器，失败不中断）"

# 安装系统依赖（OCR + 图片处理，可选，不阻塞安装）
pkg install -y tesseract imagemagick 2>/dev/null || true

# 安装 npm MCP 包（@modelcontextprotocol/* 为官方包，mcp-server-* 为社区包）
for mcp_pkg in "@modelcontextprotocol/server-github" "@modelcontextprotocol/server-filesystem" "@modelcontextprotocol/server-memory" "@modelcontextprotocol/server-sequential-thinking" "@modelcontextprotocol/server-everything" "@modelcontextprotocol/server-brave-search" "mcp-server-qrcode" "mcp-server-sqlite" "mcp-server-markdown" "mcp-server-diff" "mcp-server-weather" "mcp-server-youtube"; do
  if npm ls -g "$mcp_pkg" >/dev/null 2>&1; then
    ok "  MCP 包已安装: $mcp_pkg"
  else
    if npm install -g --no-audit --no-fund "$mcp_pkg" >/dev/null 2>&1; then
      ok "  MCP 包安装成功: $mcp_pkg"
    else
      warn "  MCP 包安装失败（跳过，可稍后手动 npm i -g $mcp_pkg）: $mcp_pkg"
    fi
  fi
done

# 复制自定义 Python MCP 脚本到 dsh 数据目录
MCP_SCRIPTS_DIR="$HOME/.dsh/mcp-scripts"
mkdir -p "$MCP_SCRIPTS_DIR"
if [ -d "$SCRIPT_DIR/scripts" ]; then
  cp "$SCRIPT_DIR/scripts/vision-mcp.py" "$MCP_SCRIPTS_DIR/" 2>/dev/null && ok "  vision-mcp 脚本已复制" || true
  cp "$SCRIPT_DIR/scripts/media-mcp.py" "$MCP_SCRIPTS_DIR/" 2>/dev/null && ok "  media-mcp 脚本已复制" || true
  cp "$SCRIPT_DIR/scripts/activity-memory-mcp.py" "$MCP_SCRIPTS_DIR/" 2>/dev/null && ok "  activity-memory-mcp 脚本已复制" || true
  cp "$SCRIPT_DIR/scripts/code-quality-mcp.py" "$MCP_SCRIPTS_DIR/" 2>/dev/null && ok "  code-quality-mcp 脚本已复制" || true
    cp "$SCRIPT_DIR/scripts/utils-mcp.py" "$MCP_SCRIPTS_DIR/" 2>/dev/null && ok "  utils-mcp 脚本已复制" || true
  chmod 755 "$MCP_SCRIPTS_DIR"/*.py 2>/dev/null || true
fi

# 渲染 MCP 段并合并到 profile 配置层（幂等：重复执行只保留一份）
MCP_TEMPLATE="$SCRIPT_DIR/config/mcp.cordis.patch.yml"
if [ -f "$MCP_TEMPLATE" ]; then
  # GITHUB_TOKEN：优先取环境变量，其次 ~/.dsh/github_token（0600）
  GH_TOKEN="${GITHUB_TOKEN:-}"
  GH_TOKEN_FILE="$HOME/.dsh/github_token"
  if [ -z "$GH_TOKEN" ] && [ -f "$GH_TOKEN_FILE" ]; then
    GH_TOKEN="$(head -c 4096 "$GH_TOKEN_FILE" | tr -d '\r\n')"
  fi
  python3 - "$MCP_TEMPLATE" "$PROFILE_PATCH" "$HOME" "$GH_TOKEN" "$MCP_SCRIPTS_DIR" <<'PY'
import sys, os
template, target, home, token, scripts_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
s = open(template, encoding='utf-8').read()
s = s.replace('{{HOME}}', home)
s = s.replace('{{MCP_SCRIPTS_DIR}}', scripts_dir)
if token:
    s = s.replace('{{GITHUB_TOKEN}}', token)
else:
    # 无 token：移除 github 服务器块（含其头部注释）
    start = s.find('- id: mcp-github')
    if start != -1:
        end = s.find('\n\n# ── MCP: Filesystem', start)
        if end == -1:
            end = len(s)
        s = s[:start] + s[end:]
    print('  [info] 未配置 GITHUB_TOKEN，跳过 github MCP（可在 ~/.dsh/github_token 放入 token 后重跑 setup.sh）')
# 幂等合并：已有 MCP 标记则整体替换其后内容，否则追加
marker = '# --- MCP servers (managed by setup.sh) ---'
old = open(target, encoding='utf-8').read() if os.path.exists(target) else ''
if marker in old:
    head = old.split(marker)[0].rstrip() + '\n'
else:
    head = old.rstrip() + ('\n' if old.strip() else '')
merged = head + marker + '\n' + s.rstrip() + '\n'
open(target, 'w', encoding='utf-8').write(merged)
print(f'  MCP 配置已合并: {target}')
PY
  ok "  MCP 配置已写入 $PROFILE_PATCH"
fi

# 复制风神插件（AGENTS.md + Skills + Agent Notes）到 dsh 数据目录
AGENTS_DIR="$HOME/.dsh/.agents"
if [ -d "$SCRIPT_DIR/.agents" ]; then
  mkdir -p "$AGENTS_DIR"
  # 复制 AGENTS.md
  cp "$SCRIPT_DIR/.agents/AGENTS.md" "$AGENTS_DIR/" 2>/dev/null && ok "  AGENTS.md 已安装"
  # 复制 Skills
  if [ -d "$SCRIPT_DIR/.agents/skills" ]; then
    mkdir -p "$AGENTS_DIR/skills"
    for skill_dir in "$SCRIPT_DIR/.agents/skills"/*/; do
      skill_name="$(basename "$skill_dir")"
      if [ -f "$skill_dir/SKILL.md" ]; then
        mkdir -p "$AGENTS_DIR/skills/$skill_name"
        cp "$skill_dir/SKILL.md" "$AGENTS_DIR/skills/$skill_name/"
        ok "  skill $skill_name 已安装"
      fi
    done
  fi
  # 复制 Notes 关键文档
  if [ -d "$SCRIPT_DIR/.agents/notes" ]; then
    mkdir -p "$AGENTS_DIR/notes"
    cp "$SCRIPT_DIR/.agents/notes/README.md" "$AGENTS_DIR/notes/" 2>/dev/null || true
    cp "$SCRIPT_DIR/.agents/notes/README.zh.md" "$AGENTS_DIR/notes/" 2>/dev/null || true
  fi
  chmod -R 600 "$AGENTS_DIR" 2>/dev/null || true
  chmod 700 "$AGENTS_DIR" "$AGENTS_DIR/skills" "$AGENTS_DIR/notes" 2>/dev/null || true
fi

# 创建第三方 API 凭证模板（不覆盖已有文件）
CRED_FILE="$HOME/.dsh/.credentials.yaml"
if [ ! -f "$CRED_FILE" ]; then
  cat > "$CRED_FILE" << 'CRED'
# DeepSeek Harness API 凭证
# 支持多个提供商，按需配置
# 设置后重启 dsh 生效

# DeepSeek API（默认）
DEEPSEEK_API_KEY: ""
DEEPSEEK_BASE_URL: "https://api.deepseek.com"

# 可选：第三方 API
# OPENAI_API_KEY: ""
# ANTHROPIC_API_KEY: ""
# OPENROUTER_API_KEY: ""
# SILICONFLOW_API_KEY: ""
CRED
  chmod 600 "$CRED_FILE"
  ok "  ~/.dsh/.credentials.yaml 模板已创建"
fi

# ------------------------------------------- 9/10 Android 编码增强预设
info "9/10 安装 Android 编码预设 (android-code, 基于官方 cordis 创造模式全面升级)"
PRESET_SRC="$SCRIPT_DIR/config/android-code"
PRESET_DST="$HOME/.dsh/.agent-presets/android-code"
if [ -d "$PRESET_SRC" ]; then
  if [ -f "$PRESET_DST/agent.cordis.yml" ]; then
    ok "  编码预设已存在（如需更新请删除 $PRESET_DST 后重跑 setup.sh）"
  else
    mkdir -p "$PRESET_DST"
    cp "$PRESET_SRC/agent.cordis.yml" "$PRESET_DST/"
    cp "$PRESET_SRC/preset.yml" "$PRESET_DST/"
    chmod 600 "$PRESET_DST"/*.yml
    ok "  编码预设已安装: $PRESET_DST"
  fi
fi

# 安装 DeepSearch 编码模式预设
DS_PRESET_SRC="$SCRIPT_DIR/config/deepsearch-coding"
DS_PRESET_DST="$HOME/.dsh/.agent-presets/deepsearch-coding"
if [ -d "$DS_PRESET_SRC" ]; then
  if [ -f "$DS_PRESET_DST/agent.cordis.yml" ]; then
    ok "  DeepSearch 编码预设已存在"
  else
    mkdir -p "$DS_PRESET_DST"
    cp "$DS_PRESET_SRC/agent.cordis.yml" "$DS_PRESET_DST/"
    cp "$DS_PRESET_SRC/preset.yml" "$DS_PRESET_DST/"
    chmod 600 "$DS_PRESET_DST"/*.yml
    ok "  DeepSearch 编码预设已安装: $DS_PRESET_DST"
  fi
fi

# ------------------------------------------------------- 10/10 前端适配(可选)
if [ -f "$SCRIPT_DIR/apply-frontend.sh" ]; then
  info "10/10 应用前端适配 + JS 性能补丁"
  bash "$SCRIPT_DIR/apply-frontend.sh"
fi

# -------------------------------------------------- JS 性能补丁(可选)
if [ -f "$SCRIPT_DIR/apply-js-patches.sh" ]; then
  info "    应用 JS 性能补丁（历史窗口瘦身 / 重连增量同步 / 静态缓存）"
  bash "$SCRIPT_DIR/apply-js-patches.sh"
fi

# ---------------------------------------------------------------- 10/10 完成
info "10/10 完成 🎉"
cat <<EOF

安装完成！接下来：
  1) 启动服务:    bash ~/dsh/start_dsh.sh
  2) 打开 Chrome: http://127.0.0.1:3080
  3) 在 Web UI 的 Models 页面填入 DeepSeek API Key
  4) 在会话预设中选择"编码模式 (Android)"启用 Code Mode 增强
  5) Web UI 工具列表将出现 mcp__github__*、mcp__vision__ocr_image、mcp__media__*、mcp__memory__*、mcp__activity_memory__* 等工具
  6) 如果配置了 GITHUB_TOKEN，Tools 列表将出现 mcp__github__* 等工具
  7) 停止服务:    bash ~/dsh/stop_dsh.sh

注意：
  - 服务只监听 127.0.0.1（本机），不走局域网。
  - 若步骤 3/10 安装在 koffi 编译报错（错误含 cnoke.cjs:844 或 koffi），
    多为 npm 版本或编译环境问题：请先 `npm i -g npm && pkg install -y cmake clang make binutils python nodejs`，
    然后重跑本脚本（步骤 1/2 已做幂等，会自动跳过已完成的步骤）。
  - 若步骤 2/10 下载 node headers 失败（网络问题），可手动执行：
    `npm_config_disturl=https://npmmirror.com/mirrors/node/ npx node-gyp install`
  - API Key 存于 ~/.dsh/.credentials.yaml（0600 权限），不进日志。
  - danger-full-access 关闭了进程沙箱（Android 无替代），仅建议个人设备使用。
  - 升级 dsh 或 Node 后需重跑本脚本。
  - MCP 服务器配置在 ~/.dsh/profiles/web/cordis.patch.yml，可手动编辑增删。
  - 新增 GITHUB_TOKEN 后重跑 setup.sh 即可启用 GitHub MCP 服务器。
EOF
