#!/data/data/com.termux/files/usr/bin/python3
"""
Utils MCP Server — 本地实用工具集（零外部依赖，替代不存在的 npm 社区包）

功能：
  - uuid_generate:       生成 UUID v4
  - hash_file:           计算文件哈希（md5/sha1/sha256/sha512）
  - hash_text:           计算文本哈希
  - base64_encode:       Base64 编码
  - base64_decode:       Base64 解码
  - regex_test:          正则表达式测试
  - regex_find:          正则表达式查找所有匹配
  - regex_replace:       正则表达式替换
  - translate_text:      本地简单词典翻译（中↔英常用词）+ 提示使用在线服务
  - emoji_search:        本地 emoji 关键词搜索
  - emoji_random:        随机 emoji

实现：MCP Protocol (JSON-RPC 2.0) over stdio
"""
import json, sys, os, re, uuid, hashlib, base64 as b64, random

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

# ── 本地词典（极简中英常用翻译，完整翻译请搭配在线服务）──────────────────

DICT_ZH_EN = {
    "你好": "hello", "世界": "world", "谢谢": "thank you", "再见": "goodbye",
    "是": "yes", "否": "no", "请": "please", "帮助": "help", "错误": "error",
    "成功": "success", "文件": "file", "目录": "directory", "文件夹": "folder",
    "代码": "code", "程序": "program", "运行": "run", "安装": "install",
    "启动": "start", "停止": "stop", "重启": "restart", "测试": "test",
    "修复": "fix", "问题": "problem", "解决": "solve", "时间": "time",
    "日期": "date", "天气": "weather", "温度": "temperature", "城市": "city",
    "手机": "phone", "电脑": "computer", "网络": "network", "速度": "speed",
    "内存": "memory", "存储": "storage", "下载": "download", "上传": "upload",
    "搜索": "search", "打开": "open", "关闭": "close", "保存": "save",
    "删除": "delete", "创建": "create", "读取": "read", "写入": "write",
}
DICT_EN_ZH = {v: k for k, v in DICT_ZH_EN.items()}

EMOJI_MAP = {
    "smile": "😊", "happy": "😄", "laugh": "😂", "love": "❤️", "heart": "❤️",
    "sad": "😢", "cry": "😭", "angry": "😡", "wink": "😉", "cool": "😎",
    "thumb": "👍", "ok": "👌", "clap": "👏", "wave": "👋", "pray": "🙏",
    "fire": "🔥", "star": "⭐", "sun": "☀️", "moon": "🌙", "rain": "🌧️",
    "cat": "🐱", "dog": "🐶", "bird": "🐦", "fish": "🐟", "bug": "🐛",
    "apple": "🍎", "banana": "🍌", "pizza": "🍕", "coffee": "☕", "beer": "🍺",
    "car": "🚗", "plane": "✈️", "rocket": "🚀", "phone": "📱", "computer": "💻",
    "book": "📖", "pencil": "✏️", "calendar": "📅", "clock": "⏰", "bell": "🔔",
    "check": "✅", "cross": "❌", "warning": "⚠️", "info": "ℹ️", "question": "❓",
    "up": "⬆️", "down": "⬇️", "left": "⬅️", "right": "➡️", "money": "💰",
    "gift": "🎁", "trophy": "🏆", "crown": "👑", "key": "🔑", "lock": "🔒",
    "bug2": "🐞", "light": "💡", "gear": "⚙️", "wrench": "🔧", "hammer": "🔨",
    "globe": "🌍", "flag": "🚩", "snow": "❄️", "flower": "🌸", "tree": "🌳",
}

# ── 工具处理函数 ─────────────────────────────────────────────────────────────

def handle_uuid_generate(args):
    n = min(max(args.get("count", 1), 1), 100)
    uuids = [str(uuid.uuid4()) for _ in range(n)]
    if n == 1:
        return {"content": [{"type": "text", "text": uuids[0]}]}
    return {"content": [{"type": "text", "text": "\n".join(f"{i+1}. {u}" for i, u in enumerate(uuids))}]}

def handle_hash_file(args):
    path = args.get("path", "")
    algorithm = args.get("algorithm", "sha256")
    if algorithm not in ("md5", "sha1", "sha256", "sha512"):
        return {"content": [{"type": "text", "text": f"不支持的算法: {algorithm}（可选 md5/sha1/sha256/sha512）"}], "isError": True}
    resolved = resolve_path(path)
    if not resolved:
        return {"content": [{"type": "text", "text": f"文件不存在: {path}"}], "isError": True}
    try:
        h = hashlib.new(algorithm)
        with open(resolved, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return {"content": [{"type": "text", "text": f"{algorithm}: {h.hexdigest()}\n文件: {resolved}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"计算失败: {str(e)}"}], "isError": True}

def handle_hash_text(args):
    text = args.get("text", "")
    algorithm = args.get("algorithm", "sha256")
    if algorithm not in ("md5", "sha1", "sha256", "sha512"):
        return {"content": [{"type": "text", "text": f"不支持的算法: {algorithm}"}], "isError": True}
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return {"content": [{"type": "text", "text": f"{algorithm}: {h.hexdigest()}"}]}

def handle_base64_encode(args):
    data = args.get("text", "")
    try:
        encoded = b64.b64encode(data.encode("utf-8")).decode("ascii")
        # URL-safe variant if requested
        if args.get("urlsafe", False):
            encoded = b64.urlsafe_b64encode(data.encode("utf-8")).decode("ascii").rstrip("=")
        return {"content": [{"type": "text", "text": encoded}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"编码失败: {str(e)}"}], "isError": True}

def handle_base64_decode(args):
    data = args.get("text", "").strip()
    try:
        # Try standard first, then urlsafe
        try:
            decoded = b64.b64decode(data).decode("utf-8")
        except Exception:
            decoded = b64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8")
        return {"content": [{"type": "text", "text": decoded}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"解码失败: {str(e)}（请检查输入是否为合法 Base64）"}], "isError": True}

def handle_regex_test(args):
    pattern = args.get("pattern", "")
    text = args.get("text", "")
    flags = args.get("flags", "")
    try:
        re_flags = 0
        if "i" in flags: re_flags |= re.IGNORECASE
        if "m" in flags: re_flags |= re.MULTILINE
        if "s" in flags: re_flags |= re.DOTALL
        matched = re.search(pattern, text, re_flags) is not None
        result = "✅ 匹配" if matched else "❌ 不匹配"
        # Show what matched
        if matched:
            m = re.search(pattern, text, re_flags)
            result += f"\n匹配内容: {m.group(0)!r}"
            if m.groups():
                result += f"\n捕获组: {m.groups()}"
        return {"content": [{"type": "text", "text": result}]}
    except re.error as e:
        return {"content": [{"type": "text", "text": f"正则错误: {str(e)}"}], "isError": True}

def handle_regex_find(args):
    pattern = args.get("pattern", "")
    text = args.get("text", "")
    flags = args.get("flags", "")
    limit = min(args.get("limit", 50), 200)
    try:
        re_flags = 0
        if "i" in flags: re_flags |= re.IGNORECASE
        if "m" in flags: re_flags |= re.MULTILINE
        if "s" in flags: re_flags |= re.DOTALL
        matches = re.findall(pattern, text, re_flags)
        total = len(matches)
        shown = matches[:limit]
        lines = [f"找到 {total} 个匹配:"]
        for i, m in enumerate(shown, 1):
            lines.append(f"  {i}. {m!r}")
        if total > limit:
            lines.append(f"  ... 以及 {total - limit} 个更多")
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}
    except re.error as e:
        return {"content": [{"type": "text", "text": f"正则错误: {str(e)}"}], "isError": True}

def handle_regex_replace(args):
    pattern = args.get("pattern", "")
    text = args.get("text", "")
    replacement = args.get("replacement", "")
    count = args.get("count", 0)
    flags = args.get("flags", "")
    try:
        re_flags = 0
        if "i" in flags: re_flags |= re.IGNORECASE
        if "m" in flags: re_flags |= re.MULTILINE
        if "s" in flags: re_flags |= re.DOTALL
        if count > 0:
            result = re.sub(pattern, replacement, text, count=count, flags=re_flags)
        else:
            result = re.sub(pattern, replacement, text, flags=re_flags)
        return {"content": [{"type": "text", "text": result}]}
    except re.error as e:
        return {"content": [{"type": "text", "text": f"正则错误: {str(e)}"}], "isError": True}

def handle_translate_text(args):
    text = args.get("text", "")
    target = args.get("target", "auto")
    if not text.strip():
        return {"content": [{"type": "text", "text": "翻译文本不能为空"}], "isError": True}

    # 本地词典查找
    results = []
    # 中文 → 英文
    if target in ("auto", "en", "english", "英文"):
        for zh, en in DICT_ZH_EN.items():
            if zh in text:
                results.append(f"{zh} → {en}")
    # 英文 → 中文
    if target in ("auto", "zh", "chinese", "中文"):
        for en, zh in DICT_EN_ZH.items():
            if re.search(r'\b' + re.escape(en) + r'\b', text, re.IGNORECASE):
                results.append(f"{en} → {zh}")

    if results:
        lines = [f"本地词典翻译（匹配 {len(results)} 个词条）:", *results, "",
                 "💡 提示: 如需完整翻译，请使用 mcp__translate 在线服务或 mcp__brave_search__* 查找翻译结果。"]
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    return {"content": [{"type": "text", "text": f"本地词典未收录「{text}」的翻译。\n💡 建议：使用 mcp__brave_search__* 搜索翻译，或配置在线翻译服务。"}]}

def handle_emoji_search(args):
    keyword = args.get("keyword", "").lower()
    if not keyword:
        return {"content": [{"type": "text", "text": f"可用关键词示例: {', '.join(list(EMOJI_MAP.keys())[:15])} ...（共 {len(EMOJI_MAP)} 个）"}]}
    matches = [(k, v) for k, v in EMOJI_MAP.items() if keyword in k]
    if not matches:
        return {"content": [{"type": "text", "text": f"未找到包含「{keyword}」的 emoji"}]}
    lines = [f"找到 {len(matches)} 个 emoji:"]
    lines.extend(f"  {v} {k}" for k, v in matches[:30])
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}

def handle_emoji_random(args):
    n = min(max(args.get("count", 1), 1), 20)
    emojis = random.sample(list(EMOJI_MAP.values()), min(n, len(EMOJI_MAP)))
    return {"content": [{"type": "text", "text": " ".join(emojis)}]}

# ── 工具注册表 ───────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "uuid_generate",
        "description": "生成 UUID v4 唯一标识符。可用于 ID、文件名、数据库主键等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "生成数量（1-100）", "default": 1}
            }
        }
    },
    {
        "name": "hash_file",
        "description": "计算文件的哈希值（MD5/SHA1/SHA256/SHA512），用于完整性校验。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "algorithm": {"type": "string", "description": "哈希算法: md5/sha1/sha256/sha512", "default": "sha256", "enum": ["md5", "sha1", "sha256", "sha512"]}
            },
            "required": ["path"]
        }
    },
    {
        "name": "hash_text",
        "description": "计算文本的哈希值（MD5/SHA1/SHA256/SHA512）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要哈希的文本"},
                "algorithm": {"type": "string", "description": "哈希算法", "default": "sha256", "enum": ["md5", "sha1", "sha256", "sha512"]}
            },
            "required": ["text"]
        }
    },
    {
        "name": "base64_encode",
        "description": "将文本编码为 Base64。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要编码的文本"},
                "urlsafe": {"type": "boolean", "description": "使用 URL 安全变体", "default": False}
            },
            "required": ["text"]
        }
    },
    {
        "name": "base64_decode",
        "description": "将 Base64 解码为文本（支持标准与 URL-safe 变体自动识别）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Base64 字符串"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "regex_test",
        "description": "测试正则表达式是否匹配文本，显示匹配内容和捕获组。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式"},
                "text": {"type": "string", "description": "要测试的文本"},
                "flags": {"type": "string", "description": "标志: i=忽略大小写, m=多行, s=点匹配换行", "default": ""}
            },
            "required": ["pattern", "text"]
        }
    },
    {
        "name": "regex_find",
        "description": "用正则表达式查找文本中的所有匹配项。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式"},
                "text": {"type": "string", "description": "要搜索的文本"},
                "flags": {"type": "string", "description": "标志: i=忽略大小写, m=多行, s=点匹配换行", "default": ""},
                "limit": {"type": "integer", "description": "返回匹配数上限", "default": 50}
            },
            "required": ["pattern", "text"]
        }
    },
    {
        "name": "regex_replace",
        "description": "用正则表达式替换文本中的匹配项。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式"},
                "text": {"type": "string", "description": "原始文本"},
                "replacement": {"type": "string", "description": "替换文本（支持 \\1 反向引用）"},
                "count": {"type": "integer", "description": "替换次数上限（0=全部）", "default": 0},
                "flags": {"type": "string", "description": "标志: i=忽略大小写, m=多行, s=点匹配换行", "default": ""}
            },
            "required": ["pattern", "text", "replacement"]
        }
    },
    {
        "name": "translate_text",
        "description": "本地词典翻译（中英常用词）。完整翻译建议使用在线服务或搜索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要翻译的文本"},
                "target": {"type": "string", "description": "目标语言: auto/en/zh", "default": "auto"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "emoji_search",
        "description": "按关键词搜索 emoji 表情符号。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "关键词（如 smile, happy, fire, rocket）"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "emoji_random",
        "description": "随机生成 emoji。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "数量（1-20）", "default": 1}
            }
        }
    },
]

HANDLERS = {
    "uuid_generate": handle_uuid_generate,
    "hash_file": handle_hash_file,
    "hash_text": handle_hash_text,
    "base64_encode": handle_base64_encode,
    "base64_decode": handle_base64_decode,
    "regex_test": handle_regex_test,
    "regex_find": handle_regex_find,
    "regex_replace": handle_regex_replace,
    "translate_text": handle_translate_text,
    "emoji_search": handle_emoji_search,
    "emoji_random": handle_emoji_random,
}

# ── 主循环 ───────────────────────────────────────────────────────────────────

def main():
    send({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "utils-mcp", "version": "1.0.0"}
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
                "serverInfo": {"name": "utils-mcp", "version": "1.0.0"}
            }})
        else:
            send({"jsonrpc": "2.0", "id": msg_id, "result": {}})

if __name__ == "__main__":
    main()