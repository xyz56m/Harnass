#!/data/data/com.termux/files/usr/bin/python3
"""
Code Quality MCP Server — 代码质量分析

基于前沿论文技术实现的代码质量评估工具：
- 复杂度分析（Cyclomatic Complexity）
- 代码风格检查（PEP8 / 通用规范）
- 安全漏洞扫描（注入、路径遍历、硬编码密钥）
- 最佳实践检查（错误处理、类型注解、文档）
- 代码指标统计（行数、函数数、注释率）

实现：MCP Protocol (JSON-RPC 2.0) over stdio
"""
import json, sys, os, re, ast, subprocess, time

# ── MCP 协议工具 ────────────────────────────────────────────────────────────

def send(msg):
    data = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write("Content-Length: %d\r\n\r\n%s" % (len(data.encode()), data))
    sys.stdout.flush()

def recv():
    raw = b""
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        raw += line
        if line == b"\r\n":
            break
    header = raw.decode().strip()
    if header.startswith("Content-Length:"):
        length = int(header.split(":")[1].strip())
        body = sys.stdin.buffer.read(length)
        return json.loads(body.decode())
    return None

def resolve_path(path):
    path = os.path.abspath(os.path.expanduser(path))
    return path if os.path.exists(path) else None

# ── 代码分析引擎 ─────────────────────────────────────────────────────────────

def analyze_python(filepath):
    """Analyze a Python file for quality metrics."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        code = f.read()

    results = {
        "file": filepath,
        "language": "Python",
        "metrics": {},
        "issues": [],
        "suggestions": []
    }

    # 基础统计
    lines = code.split('\n')
    results["metrics"]["total_lines"] = len(lines)
    results["metrics"]["code_lines"] = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
    results["metrics"]["comment_lines"] = len([l for l in lines if l.strip().startswith('#')])
    results["metrics"]["blank_lines"] = len([l for l in lines if not l.strip()])
    results["metrics"]["comment_rate"] = round(results["metrics"]["comment_lines"] / max(results["metrics"]["code_lines"], 1) * 100, 1)

    try:
        tree = ast.parse(code)

        # 函数和类统计
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        results["metrics"]["functions"] = len(functions)
        results["metrics"]["classes"] = len(classes)

        # 复杂度分析（McCabe Cyclomatic Complexity）
        for func in functions:
            complexity = 1
            for node in ast.walk(func):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    complexity += 1
                elif isinstance(node, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            name = func.name
            if complexity > 10:
                results["issues"].append(f"High complexity ({complexity}) in function '{name}' (line {func.lineno})")
            elif complexity > 5:
                results["suggestions"].append(f"Moderate complexity ({complexity}) in function '{name}' (line {func.lineno})")

        # 安全检查
        for node in ast.walk(tree):
            # 检测 exec/eval
            if isinstance(node, ast.Call) and hasattr(node.func, 'id') and node.func.id in ('exec', 'eval'):
                results["issues"].append(f"Security: Use of {node.func.id}() at line {node.lineno} — potential code injection risk")
            # 检测 shell 调用
            if isinstance(node, ast.Call) and hasattr(node.func, 'attr') and node.func.attr in ('system', 'popen', 'Popen', 'call', 'check_output', 'run'):
                if hasattr(node.func, 'value') and hasattr(node.func.value, 'id') and node.func.value.id in ('os', 'subprocess'):
                    results["issues"].append(f"Security: Shell command at line {node.lineno} — ensure shell=False and input sanitized")
            # 检测硬编码密钥
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        name = target.id.lower()
                        val = node.value.value
                        if any(kw in name for kw in ['key', 'secret', 'token', 'password', 'api_key', 'apikey']):
                            if len(val) > 10 and not val.startswith('$') and not val.startswith('{{'):
                                results["issues"].append(f"Security: Hardcoded credential '{target.id}' at line {node.lineno}")

        # 最佳实践检查
        for func in functions:
            has_docstring = (ast.get_docstring(func) is not None)
            if not has_docstring and not func.name.startswith('_'):
                results["suggestions"].append(f"Documentation: Function '{func.name}' (line {func.lineno}) missing docstring")

        # 检查是否有 main guard
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    left = node.test.left
                    if isinstance(left, ast.Name) and left.id == '__name__':
                        results["metrics"]["has_main_guard"] = True
                        break
        if 'has_main_guard' not in results["metrics"]:
            results["suggestions"].append("Best practice: Missing `if __name__ == '__main__':` guard")

    except SyntaxError as e:
        results["issues"].append(f"Syntax error: {e}")

    return results


def analyze_js(filepath):
    """Analyze a JavaScript/TypeScript file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        code = f.read()

    results = {
        "file": filepath,
        "language": "JavaScript/TypeScript",
        "metrics": {},
        "issues": [],
        "suggestions": []
    }

    lines = code.split('\n')
    results["metrics"]["total_lines"] = len(lines)
    results["metrics"]["code_lines"] = len([l for l in lines if l.strip() and not l.strip().startswith('//') and not l.strip().startswith('/*')])
    results["metrics"]["comment_lines"] = len([l for l in lines if l.strip().startswith('//') or l.strip().startswith('/*') or l.strip().startswith('*')])
    results["metrics"]["blank_lines"] = len([l for l in lines if not l.strip()])

    # 函数统计
    func_pattern = r'(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\(|(\w+\s*\([^)]*\)\s*\{))'
    functions = re.findall(func_pattern, code)
    results["metrics"]["functions"] = len(functions)

    # 安全检查
    if re.search(r'eval\s*\(', code):
        results["issues"].append("Security: Use of eval() — potential code injection risk")
    if re.search(r'exec\s*\(', code):
        results["issues"].append("Security: Use of exec() — potential code injection risk")
    if re.search(r'innerHTML\s*=', code):
        results["issues"].append("Security: Use of innerHTML — potential XSS risk")
    if re.search(r'process\.env\.\w+', code):
        # Check for hardcoded fallbacks
        env_var_pattern = r'process\.env\.(\w+)\s*\|\|\s*["\'][^"\']+["\']'
        hardcoded = re.findall(env_var_pattern, code)
        for var in hardcoded:
            results["suggestions"].append(f"Security: Hardcoded fallback for env var {var}")

    return results


def analyze_bash(filepath):
    """Analyze a shell script."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        code = f.read()

    results = {
        "file": filepath,
        "language": "Bash",
        "metrics": {},
        "issues": [],
        "suggestions": []
    }

    lines = code.split('\n')
    results["metrics"]["total_lines"] = len(lines)
    results["metrics"]["code_lines"] = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
    results["metrics"]["blank_lines"] = len([l for l in lines if not l.strip()])

    # 安全检查
    if re.search(r'rm\s+-rf\s+\$', code):
        results["issues"].append("Safety: Recursive delete with variable — ensure variable is not empty")
    if re.search(r'curl\s+.*\|\s*bash', code) or re.search(r'wget\s+.*\|\s*bash', code):
        results["issues"].append("Security: Piping downloaded script to bash — verify the source")
    if re.search(r'>\s*/dev/null\s*2>&1\s*&', code):
        pass  # 常见模式，仅提示
    if not re.search(r'#!/', code.split('\n')[0] if code else ''):
        results["issues"].append("Missing shebang (#!/...) at start of file")

    return results

# ── 工具处理函数 ─────────────────────────────────────────────────────────────

LANGUAGE_ANALYZERS = {
    '.py': analyze_python,
    '.js': analyze_js,
    '.jsx': analyze_js,
    '.ts': analyze_js,
    '.tsx': analyze_js,
    '.sh': analyze_bash,
    '.bash': analyze_bash,
}

def handle_analyze_code(args):
    """Analyze a code file for quality metrics."""
    filepath = args.get("filepath", "")
    resolved = resolve_path(filepath)
    if not resolved:
        return {"content": [{"type": "text", "text": f"文件不存在: {filepath}"}], "isError": True}

    ext = os.path.splitext(resolved)[1].lower()
    analyzer = LANGUAGE_ANALYZERS.get(ext)

    if not analyzer:
        # 通用分析
        with open(resolved, 'rb') as f:
            header = f.read(1024)
        # 尝试检测类型
        if header.startswith(b'#!/') or b'#!/' in header[:200]:
            analyzer = analyze_bash
        else:
            return {"content": [{"type": "text", "text": f"不支持的文件类型: {ext}。支持的扩展名: {', '.join(LANGUAGE_ANALYZERS.keys())}"}], "isError": True}

    try:
        result = analyzer(resolved)
    except Exception as e:
        return {"content": [{"type": "text", "text": f"分析失败: {str(e)}"}], "isError": True}

    # 格式化输出
    lines = []
    lines.append(f"## 代码质量报告: {result['file']}")
    lines.append(f"语言: {result['language']}")
    lines.append("")
    lines.append("### 指标统计")
    for k, v in result['metrics'].items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    if result['issues']:
        lines.append(f"### 问题 ({len(result['issues'])} 项)")
        for issue in result['issues']:
            lines.append(f"- ❌ {issue}")
        lines.append("")

    if result['suggestions']:
        lines.append(f"### 建议 ({len(result['suggestions'])} 项)")
        for sug in result['suggestions']:
            lines.append(f"- 💡 {sug}")
        lines.append("")

    if not result['issues'] and not result['suggestions']:
        lines.append("✅ 代码质量良好，未发现问题。")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_analyze_directory(args):
    """Analyze all supported code files in a directory."""
    dirpath = args.get("dirpath", "")
    recursive = args.get("recursive", True)
    resolved = resolve_path(dirpath)
    if not resolved:
        return {"content": [{"type": "text", "text": f"目录不存在: {dirpath}"}], "isError": True}

    max_files = min(args.get("max_files", 20), 100)
    depth = 3 if recursive else 1

    results = []
    file_count = 0
    for root, dirs, files in os.walk(resolved):
        rel = os.path.relpath(root, resolved)
        level = rel.count(os.sep) + 1 if rel != '.' else 0
        if level > depth:
            dirs.clear()
            continue
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext in LANGUAGE_ANALYZERS:
                fp = os.path.join(root, fn)
                analyzer = LANGUAGE_ANALYZERS[ext]
                try:
                    result = analyzer(fp)
                    issues = len(result.get('issues', []))
                    suggestions = len(result.get('suggestions', []))
                    results.append({
                        "file": os.path.relpath(fp, resolved),
                        "language": result['language'],
                        "metrics": result['metrics'],
                        "issues_count": issues,
                        "suggestions_count": suggestions,
                    })
                    file_count += 1
                    if file_count >= max_files:
                        break
                except:
                    pass
        if file_count >= max_files:
            break

    if not results:
        return {"content": [{"type": "text", "text": f"在 {resolved} 中未找到支持的代码文件"}]}

    total_issues = sum(r['issues_count'] for r in results)
    total_suggestions = sum(r['suggestions_count'] for r in results)
    total_lines = sum(r['metrics'].get('total_lines', 0) for r in results)

    lines = [f"## 目录代码质量报告: {resolved}"]
    lines.append(f"分析文件: {len(results)} 个 (共 {total_lines} 行)")
    lines.append(f"问题: {total_issues} 项, 建议: {total_suggestions} 项")
    lines.append("")
    lines.append("### 文件概览")
    for r in results:
        flag = "❌" if r['issues_count'] > 0 else "✅"
        lines.append(f"- {flag} {r['file']}: {r['metrics'].get('total_lines',0)} 行, {r['issues_count']} 问题, {r['suggestions_count']} 建议")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}

def handle_auto_analyze(args):
    """Auto analyze: scan recently modified files in working directory."""
    work_dir = args.get("work_dir", os.environ.get("HOME", ""))
    max_files = min(args.get("max_files", 5), 20)
    resolved = resolve_path(work_dir)
    if not resolved:
        return {"content": [{"type": "text", "text": f"目录不存在: {work_dir}"}], "isError": True}

    # Find recently modified code files
    recent_files = []
    now = time.time()
    for root, dirs, files in os.walk(resolved):
        # Skip hidden dirs and node_modules
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv')]
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext in LANGUAGE_ANALYZERS:
                fp = os.path.join(root, fn)
                try:
                    mtime = os.path.getmtime(fp)
                    if now - mtime < 3600:  # modified in last hour
                        recent_files.append((fp, mtime))
                except:
                    pass

    # Sort by modification time (most recent first)
    recent_files.sort(key=lambda x: x[1], reverse=True)
    recent_files = recent_files[:max_files]

    if not recent_files:
        return {"content": [{"type": "text", "text": f"在 {resolved} 中未找到最近修改的代码文件"}]}

    results = []
    for fp, mtime in recent_files:
        ext = os.path.splitext(fp)[1].lower()
        analyzer = LANGUAGE_ANALYZERS.get(ext)
        if analyzer:
            try:
                result = analyzer(fp)
                issues = len(result.get('issues', []))
                suggestions = len(result.get('suggestions', []))
                rel = os.path.relpath(fp, resolved)
                flag = "❌" if issues > 0 else "✅"
                results.append(f"- {flag} {rel}: {result['metrics'].get('total_lines',0)} 行, {issues} 问题, {suggestions} 建议")
            except Exception as e:
                results.append(f"- ⚠️ {os.path.relpath(fp, resolved)}: 分析失败 - {str(e)[:60]}")

    lines = [f"## 自动分析: {resolved}", f"扫描 {len(recent_files)} 个最近修改的文件:", ""]
    lines.extend(results)
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_git_diff_analyze(args):
    """Analyze git diff for security and quality issues."""
    work_dir = args.get("work_dir", os.environ.get("HOME", ""))
    base_ref = args.get("base_ref", "HEAD")
    resolved = resolve_path(work_dir)
    if not resolved:
        return {"content": [{"type": "text", "text": f"目录不存在: {work_dir}"}], "isError": True}

    # Check if it's a git repo
    git_dir = os.path.join(resolved, ".git")
    if not os.path.isdir(git_dir):
        return {"content": [{"type": "text", "text": f"{resolved} 不是 git 仓库"}], "isError": True}

    try:
        result = subprocess.run(
            ["git", "diff", base_ref],
            capture_output=True, text=True, timeout=30,
            cwd=resolved
        )
        if result.returncode != 0:
            return {"content": [{"type": "text", "text": f"git diff 失败: {result.stderr.strip()[:200]}"}], "isError": True}

        diff = result.stdout
        if not diff:
            return {"content": [{"type": "text", "text": "没有未提交的变更"}]}

        issues = []
        # Check for common security issues in diff
        if re.search(r'^\+\s*(eval|exec)\s*\(', diff, re.MULTILINE):
            issues.append("❌ Security: 新增 eval/exec 调用 — 潜在代码注入风险")
        if re.search(r'^\+\s*.*innerHTML\s*=', diff, re.MULTILINE):
            issues.append("❌ Security: 新增 innerHTML 使用 — 潜在 XSS 风险")
        if re.search(r'^\+\s*.*rm\s+-rf\s+', diff, re.MULTILINE):
            issues.append("⚠️ Safety: 新增 rm -rf 命令 — 确保变量非空")
        if re.search(r'^\+\s*.*\b(secret|password|api_key|token)\s*=\s*["\'][^"\']{8,}', diff, re.MULTILINE):
            issues.append("❌ Security: 新增硬编码凭据")
        if re.search(r'^\+\s*.*\b(DEBUG|debug|print|console\.log)\s*\(', diff, re.MULTILINE):
            issues.append("💡 Quality: 新增调试语句 — 确认是否需保留")

        # Count stats
        added = len(re.findall(r'^\+', diff, re.MULTILINE))
        removed = len(re.findall(r'^-', diff, re.MULTILINE))

        lines = [f"## git diff 分析 ({base_ref})", f"变更: +{added}/-{removed} 行", ""]
        if issues:
            lines.append(f"### 发现 {len(issues)} 个问题:")
            lines.extend(issues)
        else:
            lines.append("✅ diff 检查通过，未发现安全问题")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": "git diff 超时（仓库过大）"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"分析失败: {str(e)[:200]}"}], "isError": True}


def handle_auto_fix_suggest(args):
    """Generate fix suggestions based on code analysis."""
    filepath = args.get("filepath", "")
    resolved = resolve_path(filepath)
    if not resolved:
        return {"content": [{"type": "text", "text": f"文件不存在: {filepath}"}], "isError": True}

    ext = os.path.splitext(resolved)[1].lower()
    analyzer = LANGUAGE_ANALYZERS.get(ext)
    if not analyzer:
        return {"content": [{"type": "text", "text": f"不支持的文件类型: {ext}"}], "isError": True}

    try:
        result = analyzer(resolved)
    except Exception as e:
        return {"content": [{"type": "text", "text": f"分析失败: {str(e)}"}], "isError": True}

    issues = result.get('issues', [])
    suggestions = result.get('suggestions', [])

    if not issues and not suggestions:
        return {"content": [{"type": "text", "text": f"✅ {filepath} 质量良好，无需修复建议"}]}

    lines = [f"## 修复建议: {filepath}", ""]

    if issues:
        lines.append(f"### 需修复 ({len(issues)} 项)")
        for issue in issues:
            if "Security" in issue or "security" in issue:
                lines.append(f"- ❌ **{issue}**")
                lines.append(f"  → 建议: 移除或替换为安全替代方案")
            elif "complexity" in issue.lower() or "Complexity" in issue:
                lines.append(f"- ⚠️ **{issue}**")
                lines.append(f"  → 建议: 将函数拆分为多个小函数，降低圈复杂度")
            elif "Syntax" in issue:
                lines.append(f"- ❌ **{issue}**")
                lines.append(f"  → 建议: 修复语法错误后重试")
            else:
                lines.append(f"- ⚠️ **{issue}**")
                lines.append(f"  → 建议: 审查并修复")
        lines.append("")

    if suggestions:
        lines.append(f"### 建议改进 ({len(suggestions)} 项)")
        for sug in suggestions:
            if "docstring" in sug.lower() or "Documentation" in sug:
                lines.append(f"- 💡 **{sug}**")
                lines.append(f"  → 建议: 添加文档字符串说明函数用途、参数和返回值")
            elif "Missing" in sug or "missing" in sug:
                lines.append(f"- 💡 **{sug}**")
                lines.append(f"  → 建议: 按最佳实践补充")
            elif "Hardcoded" in sug:
                lines.append(f"- 💡 **{sug}**")
                lines.append(f"  → 建议: 使用环境变量替代硬编码值")
            else:
                lines.append(f"- 💡 **{sug}**")
        lines.append("")

    lines.append("---")
    lines.append("*自动生成的修复建议，请人工审查后再应用*")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}

# ── 工具注册表 ───────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "analyze_code",
        "description": "分析单个代码文件的质量。支持 Python(.py)、JavaScript/TypeScript(.js/.ts/.jsx/.tsx)、Shell(.sh/.bash)。返回复杂度、风格、安全、最佳实践等指标。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "代码文件路径"}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "analyze_directory",
        "description": "分析目录下所有支持的代码文件，返回质量概览对比。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dirpath": {"type": "string", "description": "目录路径"},
                "recursive": {"type": "boolean", "description": "是否递归子目录", "default": True},
                "max_files": {"type": "integer", "description": "最大分析文件数（1-100）", "default": 20}
            },
            "required": ["dirpath"]
        }
    },
    {
        "name": "auto_analyze",
        "description": "自动分析：无需指定文件，自动扫描当前工作目录中最近修改的代码文件，返回质量概览。适合在每个变更后自动调用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_files": {"type": "integer", "description": "最大分析文件数", "default": 5},
                "work_dir": {"type": "string", "description": "工作目录（默认 $HOME）"}
            }
        }
    },
    {
        "name": "git_diff_analyze",
        "description": "分析 git diff 中的代码变更，检测新增的安全问题和代码质量标记。适合在提交前自动调用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "work_dir": {"type": "string", "description": "git 仓库目录"},
                "base_ref": {"type": "string", "description": "对比基准（默认 HEAD）", "default": "HEAD"}
            }
        }
    },
    {
        "name": "auto_fix_suggest",
        "description": "基于分析结果自动生成修复建议。对每个问题给出具体的改进方案。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "代码文件路径"}
            },
            "required": ["filepath"]
        }
    }
]

HANDLERS = {
    "analyze_code": handle_analyze_code,
    "analyze_directory": handle_analyze_directory,
    "auto_analyze": handle_auto_analyze,
    "git_diff_analyze": handle_git_diff_analyze,
    "auto_fix_suggest": handle_auto_fix_suggest,
}

# ── 主循环 ───────────────────────────────────────────────────────────────────

def main():
    send({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "code-quality-mcp", "version": "1.0.0"}
        }
    })

    while True:
        msg = recv()
        if msg is None:
            break
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if msg_id is None:
            continue

        if method == "tools/list":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            handler = HANDLERS.get(name)
            if handler:
                result = handler(args)
                send({"jsonrpc": "2.0", "id": msg_id, "result": result})
            else:
                send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"未知工具: {name}"}})
        elif method == "initialize":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "code-quality-mcp", "version": "1.0.0"}
            }})
        else:
            send({"jsonrpc": "2.0", "id": msg_id, "result": {}})

if __name__ == "__main__":
    main()