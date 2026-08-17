#!/data/data/com.termux/files/usr/bin/python3
"""
Activity Memory MCP Server — 活动记忆

跨会话持久化记忆：记住用户偏好、学习记录、代码习惯、项目上下文。
数据以 JSON 格式存储在 ~/.dsh/activity-memory/ 目录下。

功能：
  - remember: 记住一条信息（分类存储）
  - recall: 回忆某类记忆或搜索关键词
  - list_memories: 列出所有记忆类别及条数
  - forget: 删除特定记忆
  - clear_category: 清空某类所有记忆

实现：MCP Protocol (JSON-RPC 2.0) over stdio
"""
import json, sys, os, time, glob

# ── 存储目录 ─────────────────────────────────────────────────────────────────

HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
MEMORY_DIR = os.path.join(HOME, ".dsh", "activity-memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

# 记忆类别
CATEGORIES = {
    "user_pref": "用户偏好（语言、主题、快捷键等）",
    "learning_record": "学习记录（已学技能、知识点、兴趣方向）",
    "code_habit": "代码习惯（常用框架、编码风格、工具链）",
    "project_context": "项目上下文（当前项目、目标、进度）",
    "general": "通用记忆（其他）",
}

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

# ── 存储引擎 ─────────────────────────────────────────────────────────────────

def _cat_file(category):
    """Get the file path for a category."""
    return os.path.join(MEMORY_DIR, f"{category}.json")

def _load_category(category):
    """Load all memories in a category."""
    fp = _cat_file(category)
    if os.path.exists(fp):
        try:
            with open(fp, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def _save_category(category, memories):
    """Save all memories for a category."""
    fp = _cat_file(category)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)
    os.chmod(fp, 0o600)

def _next_id(memories):
    """Generate next unique ID."""
    ids = [m.get("id", 0) for m in memories]
    return (max(ids) + 1) if ids else 1

# ── 工具处理函数 ─────────────────────────────────────────────────────────────

def handle_remember(args):
    """记住一条信息。"""
    category = args.get("category", "general")
    if category not in CATEGORIES:
        valid = ", ".join(CATEGORIES.keys())
        return {"content": [{"type": "text", "text": f"无效类别 {category}，有效类别: {valid}"}], "isError": True}

    content = args.get("content", "")
    if not content.strip():
        return {"content": [{"type": "text", "text": "记忆内容不能为空"}], "isError": True}

    tags = args.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    memories = _load_category(category)
    entry = {
        "id": _next_id(memories),
        "content": content,
        "tags": tags,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    memories.append(entry)
    _save_category(category, memories)

    cat_name = CATEGORIES.get(category, category)
    return {"content": [{"type": "text", "text": f"✅ 已记住 ({cat_name}): #{entry['id']} — {content[:100]}" + ("..." if len(content) > 100 else "")}]}

def handle_recall(args):
    """回忆记忆。支持按类别、关键词搜索。"""
    category = args.get("category", "")  # 空=全部类别
    keyword = args.get("keyword", "")
    limit = min(args.get("limit", 50), 200)

    results = []
    cats_to_search = [category] if category and category in CATEGORIES else list(CATEGORIES.keys())

    for cat in cats_to_search:
        memories = _load_category(cat)
        for m in memories:
            if keyword:
                kw = keyword.lower()
                if kw in m.get("content", "").lower():
                    results.append((cat, m))
                elif any(kw in t.lower() for t in m.get("tags", [])):
                    results.append((cat, m))
            else:
                results.append((cat, m))

    # 按更新时间倒序
    results.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
    results = results[:limit]

    if not results:
        if keyword:
            return {"content": [{"type": "text", "text": f"未找到包含「{keyword}」的记忆"}]}
        else:
            return {"content": [{"type": "text", "text": "暂无记忆，请先使用 remember 工具添加记忆"}]}

    lines = [f"找到 {len(results)} 条记忆:"]
    for cat, m in results:
        cat_name = CATEGORIES.get(cat, cat)
        tags_str = f" [{', '.join(m.get('tags', []))}]" if m.get("tags") else ""
        content_preview = m["content"][:120] + ("..." if len(m["content"]) > 120 else "")
        lines.append(f"  #{m['id']} [{cat_name}]{tags_str} ({m.get('created_at','')})")
        lines.append(f"    {content_preview}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}

def handle_list_memories(args):
    """列出所有记忆类别及条数。"""
    counts = []
    total = 0
    for cat, cat_name in CATEGORIES.items():
        memories = _load_category(cat)
        count = len(memories)
        total += count
        if count > 0:
            counts.append(f"  {cat_name} ({cat}): {count} 条")
        else:
            counts.append(f"  {cat_name} ({cat}): 空")

    lines = [f"活动记忆概览 (总计 {total} 条，存储于 {MEMORY_DIR}):"]
    lines.extend(counts)
    lines.append(f"\n使用 recall 工具查看具体记忆，使用 remember 工具添加新记忆。")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}

def handle_forget(args):
    """删除特定记忆。"""
    category = args.get("category", "")
    mem_id = args.get("id", 0)

    if category not in CATEGORIES:
        return {"content": [{"type": "text", "text": f"无效类别: {category}"}], "isError": True}

    memories = _load_category(category)
    found = [m for m in memories if m.get("id") == mem_id]
    if not found:
        return {"content": [{"type": "text", "text": f"未找到 #{mem_id} 在 {CATEGORIES.get(category, category)} 中"}], "isError": True}

    memories = [m for m in memories if m.get("id") != mem_id]
    _save_category(category, memories)
    return {"content": [{"type": "text", "text": f"✅ 已删除 #{mem_id}: {found[0]['content'][:80]}"}]}

def handle_clear_category(args):
    """清空某类记忆。"""
    category = args.get("category", "")
    confirm = args.get("confirm", False)

    if category not in CATEGORIES:
        return {"content": [{"type": "text", "text": f"无效类别: {category}"}], "isError": True}

    if not confirm:
        count = len(_load_category(category))
        return {"content": [{"type": "text", "text": f"⚠️ 确认要清空「{CATEGORIES.get(category, category)}」({count} 条)？设置 confirm=true 来确认"}], "isError": True}

    _save_category(category, [])
    return {"content": [{"type": "text", "text": f"✅ 已清空「{CATEGORIES.get(category, category)}」"}]}

# ── 工具注册表 ───────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "remember",
        "description": "记住一条信息到活动记忆。支持分类存储，AI 应主动使用此工具记住用户偏好、习惯、项目上下文等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要记住的内容"},
                "category": {
                    "type": "string",
                    "description": "记忆类别: user_pref=用户偏好, learning_record=学习记录, code_habit=代码习惯, project_context=项目上下文, general=通用",
                    "default": "general",
                    "enum": list(CATEGORIES.keys())
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签数组，便于搜索（如 [\"python\", \"django\"]）",
                    "default": []
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "recall",
        "description": "回忆已存储的活动记忆。支持按类别筛选和关键词搜索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "记忆类别筛选（空=全部类别）",
                    "enum": ["", *list(CATEGORIES.keys())],
                    "default": ""
                },
                "keyword": {"type": "string", "description": "关键词搜索", "default": ""},
                "limit": {"type": "integer", "description": "返回条数上限", "default": 50}
            }
        }
    },
    {
        "name": "list_memories",
        "description": "列出所有记忆类别及条数概览。",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "forget",
        "description": "删除一条特定记忆。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "记忆类别", "enum": list(CATEGORIES.keys())},
                "id": {"type": "integer", "description": "要删除的记忆 ID"}
            },
            "required": ["category", "id"]
        }
    },
    {
        "name": "clear_category",
        "description": "清空某类所有记忆。需要二次确认（confirm=true）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "要清空的类别", "enum": list(CATEGORIES.keys())},
                "confirm": {"type": "boolean", "description": "确认操作，必须为 true 才能执行", "default": False}
            },
            "required": ["category"]
        }
    }
]

HANDLERS = {
    "remember": handle_remember,
    "recall": handle_recall,
    "list_memories": handle_list_memories,
    "forget": handle_forget,
    "clear_category": handle_clear_category,
}

# ── 主循环 ───────────────────────────────────────────────────────────────────

def main():
    send({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "activity-memory-mcp", "version": "1.0.0"}
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
                "serverInfo": {"name": "activity-memory-mcp", "version": "1.0.0"}
            }})
        else:
            send({"jsonrpc": "2.0", "id": msg_id, "result": {}})

if __name__ == "__main__":
    main()